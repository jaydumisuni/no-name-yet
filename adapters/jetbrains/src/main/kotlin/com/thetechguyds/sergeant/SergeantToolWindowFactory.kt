package com.thetechguyds.sergeant

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.intellij.ide.util.PropertiesComponent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileTypes.PlainTextFileType
import com.intellij.openapi.ide.CopyPasteManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Disposer
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFileManager
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.testFramework.LightVirtualFile
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.jcef.JBCefApp
import com.intellij.ui.jcef.JBCefBrowser
import com.intellij.ui.jcef.JBCefBrowserBase
import com.intellij.ui.jcef.JBCefJSQuery
import com.intellij.util.ui.JBUI
import java.awt.BorderLayout
import java.awt.Font
import java.awt.datatransfer.StringSelection
import java.io.File
import java.nio.charset.StandardCharsets
import java.time.Instant
import javax.swing.JButton
import javax.swing.JPanel

private val semanticSettingKeys = mapOf(
    "policy" to "sergeant.llm.policy",
    "provider" to "sergeant.llm.provider",
    "baseUrl" to "sergeant.llm.baseUrl",
    "model" to "sergeant.llm.model",
    "protocol" to "sergeant.llm.protocol",
    "council" to "sergeant.llm.council",
)

class SergeantToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = if (JBCefApp.isSupported()) SergeantCommandCenterPanel(project) else SergeantFallbackPanel(project)
        val content = ContentFactory.getInstance().createContent(panel, "Command Center", false)
        toolWindow.contentManager.addContent(content)
    }
}

private class SergeantCommandCenterPanel(private val project: Project) : JPanel(BorderLayout()) {
    private val gson = Gson()
    private val browser = JBCefBrowser()
    private val query = JBCefJSQuery.create(browser as JBCefBrowserBase)
    private var status = "Standing By"
    private var running = ""
    private var runningTitle = ""
    private var lastOutput = ""
    private var lastResult: Map<String, Any?>? = null
    private val history = mutableListOf<Map<String, Any?>>()

    init {
        border = JBUI.Borders.empty()
        add(browser.component, BorderLayout.CENTER)
        Disposer.register(project, query)
        Disposer.register(project, browser)
        query.addHandler { payload ->
            handleMessage(payload)
            null
        }
        val html = loadCommandCenterHtml().replace(
            "<!-- SERGEANT_HOST_BOOTSTRAP -->",
            "<script>window.sergeantHostSend=(payload)=>{${query.inject("payload")}};</script>",
        )
        browser.loadHTML(html, "file://sergeant-command-center-v2.html")
    }

    private fun handleMessage(payload: String) {
        try {
            val message = JsonParser.parseString(payload).asJsonObject
            when (message.get("type")?.asString.orEmpty()) {
                "ready", "refresh" -> sendState()
                "run" -> {
                    saveSemanticSettings(message.getAsJsonObject("settings"))
                    runMission(message.get("action")?.asString.orEmpty())
                }
                "openLast" -> openLastReport()
                "copyLast" -> copyLastReport()
                "exportLast" -> exportLastReport()
                "saveSettings" -> {
                    saveSemanticSettings(message.getAsJsonObject("settings"))
                    sendState("Cpl reasoning settings saved.")
                }
                "selectWorkspace" -> sendState()
            }
        } catch (error: Exception) {
            status = "Needs Attention"
            sendState(error.message ?: error.javaClass.simpleName)
        }
    }

    private fun saveSemanticSettings(settings: JsonObject?) {
        if (settings == null) return
        val properties = PropertiesComponent.getInstance(project)
        for ((publicKey, storageKey) in semanticSettingKeys) {
            val value = settings.get(publicKey)?.takeIf { !it.isJsonNull }?.asString ?: continue
            properties.setValue(storageKey, value)
        }
    }

    private fun semanticSettings(): Map<String, String> {
        val properties = PropertiesComponent.getInstance(project)
        val defaults = mapOf(
            "policy" to "preferred",
            "provider" to "auto",
            "baseUrl" to "",
            "model" to "",
            "protocol" to "auto",
            "council" to "adaptive",
        )
        return semanticSettingKeys
            .mapValues { (publicKey, storageKey) -> properties.getValue(storageKey) ?: defaults.getValue(publicKey) }
            .mapValues { (publicKey, value) ->
                when {
                    publicKey == "provider" && value == "fcc" -> "cpl"
                    publicKey == "council" && value == "always" -> "maximum"
                    else -> value
                }
            }
    }

    private fun runMission(action: String) {
        if (action.isBlank()) return
        status = "Running"
        running = action
        runningTitle = missionTitle(action)
        sendState()
        ApplicationManager.getApplication().executeOnPooledThread {
            val result = SergeantRunner.run(project, action)
            ApplicationManager.getApplication().invokeLater {
                if (project.isDisposed) return@invokeLater
                lastOutput = result.output
                val verdict = if (result.exitCode == 0) "PASS" else "NEEDS ATTENTION"
                val summary = mapOf(
                    "verdict" to verdict,
                    "status" to verdict,
                    "exitCode" to result.exitCode,
                    "findingCount" to 0,
                    "action" to if (result.exitCode == 0) "Review evidence" else "Inspect report",
                )
                val item = mapOf<String, Any?>(
                    "id" to "#${System.currentTimeMillis().toString().takeLast(6)}",
                    "title" to result.title,
                    "mission" to result.title,
                    "result" to verdict,
                    "verdict" to verdict,
                    "finishedAt" to Instant.now().toString(),
                    "date" to java.time.ZonedDateTime.now().toString(),
                    "duration" to "Runtime",
                    "summary" to summary,
                    "findings" to extractEvidence(result.output),
                    "justFinished" to true,
                )
                history.add(0, item)
                while (history.size > 50) history.removeLast()
                lastResult = item
                status = if (result.exitCode == 0) "Complete" else "Needs Attention"
                running = ""
                runningTitle = ""
                sendState(if (result.exitCode == 0) "" else "Mission completed with exit code ${result.exitCode}.")
            }
        }
    }

    private fun sendState(notice: String = "") {
        val root = project.basePath.orEmpty()
        val branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").ifBlank { "not-git" }
        val changed = git(root, "status", "--porcelain").lineSequence().count { it.isNotBlank() }
        val state = mapOf<String, Any?>(
            "status" to status,
            "running" to running,
            "runningTitle" to runningTitle,
            "progress" to if (running.isNotBlank()) 36 else if (lastResult != null) 100 else 0,
            "platform" to "JetBrains",
            "workspace" to project.name,
            "root" to root,
            "branch" to branch,
            "changedFilesCount" to changed,
            "last" to lastResult,
            "history" to history,
            "notice" to notice,
            "error" to (notice.isNotBlank() && status == "Needs Attention"),
            "settings" to semanticSettings(),
        )
        val json = gson.toJson(state)
        browser.cefBrowser.executeJavaScript(
            "window.postMessage({type:'sergeantState',state:$json}, '*');",
            browser.cefBrowser.url,
            0,
        )
    }

    private fun openLastReport() {
        if (lastOutput.isBlank()) {
            sendState("No Sergeant report is available yet.")
            return
        }
        val file = LightVirtualFile("sergeant-report.txt", PlainTextFileType.INSTANCE, lastOutput)
        FileEditorManager.getInstance(project).openFile(file, true)
    }

    private fun copyLastReport() {
        if (lastOutput.isBlank()) {
            sendState("No Sergeant report is available to copy.")
            return
        }
        CopyPasteManager.getInstance().setContents(StringSelection(lastOutput))
        sendState("Sergeant report copied.")
    }

    private fun exportLastReport() {
        val root = project.basePath
        if (root.isNullOrBlank() || lastOutput.isBlank()) {
            sendState("No Sergeant report is available to export.")
            return
        }
        val target = File(root, "sergeant-report.txt")
        target.writeText(lastOutput, StandardCharsets.UTF_8)
        LocalFileSystem.getInstance().refreshAndFindFileByIoFile(target)
        VirtualFileManager.getInstance().syncRefresh()
        sendState("Sergeant report exported to ${target.path}.")
    }

    private fun loadCommandCenterHtml(): String {
        fun resource(name: String): String {
            val stream = javaClass.getResourceAsStream("/$name")
                ?: error("Bundled Sergeant resource '$name' is missing.")
            return stream.bufferedReader(StandardCharsets.UTF_8).use { it.readText() }
        }
        return resource("sergeant-command-center-v2.html")
            .replace("/* SERGEANT_CSS */", resource("sergeant-command-center-v2.css"))
            .replace("/* SERGEANT_RESPONSIVE_CSS */", resource("sergeant-command-center-v2-responsive.css"))
            .replace("// SERGEANT_JS", resource("sergeant-command-center-v2.js"))
    }

    private fun git(root: String, vararg args: String): String {
        if (root.isBlank()) return ""
        return try {
            val process = ProcessBuilder(listOf("git") + args)
                .directory(File(root))
                .redirectErrorStream(true)
                .start()
            val output = process.inputStream.bufferedReader().readText()
            process.waitFor()
            output.trim()
        } catch (_: Exception) {
            ""
        }
    }

    private fun extractEvidence(output: String): List<Map<String, String>> = output
        .lineSequence()
        .map(String::trim)
        .filter { it.isNotBlank() }
        .take(12)
        .map { mapOf("message" to it) }
        .toList()

    private fun missionTitle(action: String): String = when (action) {
        "reviewWorkspace" -> "Sergeant workspace review"
        "appReviewWorkspace" -> "Sergeant app bridge review"
        "reviewCurrentFile" -> "Sergeant current file review"
        "reviewChangedFiles" -> "Sergeant changed files review"
        "v2Mission" -> "Sergeant V2 mission"
        "proofSuite" -> "Sergeant proof suite"
        "finalProof" -> "Sergeant final proof"
        "verifyStandard" -> "Sergeant standard verification"
        "battleTests" -> "Sergeant battle tests"
        "ideBenchContract" -> "Sergeant IDE Bench contract"
        else -> "Sergeant mission"
    }
}

private class SergeantFallbackPanel(private val project: Project) : JPanel(BorderLayout()) {
    private val output = JBTextArea().apply {
        isEditable = false
        lineWrap = false
        font = Font(Font.MONOSPACED, Font.PLAIN, 12)
        text = "Sergeant 0.4.0-preview\n\nJCEF is unavailable. Native fallback is ready to run deterministic review and Cpl specialist reasoning for ${project.name}."
    }
    private val runButton = JButton("Review Project")

    init {
        border = JBUI.Borders.empty(12)
        val header = JPanel(BorderLayout()).apply {
            border = JBUI.Borders.emptyBottom(10)
            add(JBLabel("Sergeant Command Center").apply { font = font.deriveFont(Font.BOLD, 16f) }, BorderLayout.NORTH)
            add(JBLabel("Evidence before opinion. Verification before release."), BorderLayout.CENTER)
            add(runButton, BorderLayout.SOUTH)
        }
        add(header, BorderLayout.NORTH)
        add(JBScrollPane(output), BorderLayout.CENTER)
        runButton.addActionListener { runReview() }
    }

    private fun runReview() {
        runButton.isEnabled = false
        output.text = "Running Sergeant deterministic review and Cpl specialist reasoning…"
        ApplicationManager.getApplication().executeOnPooledThread {
            val result = SergeantRunner.review(project)
            ApplicationManager.getApplication().invokeLater {
                if (project.isDisposed) return@invokeLater
                output.text = "Exit code: ${result.exitCode}\n\n${result.output}"
                output.caretPosition = 0
                runButton.isEnabled = true
            }
        }
    }
}
