package com.thetechguyds.sergeant

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextArea
import com.intellij.ui.content.ContentFactory
import com.intellij.util.ui.JBUI
import java.awt.BorderLayout
import java.awt.Font
import javax.swing.JButton
import javax.swing.JPanel

class SergeantToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = SergeantPanel(project)
        val content = ContentFactory.getInstance().createContent(panel, "Command Center", false)
        toolWindow.contentManager.addContent(content)
    }
}

private class SergeantPanel(private val project: Project) : JPanel(BorderLayout()) {
    private val output = JBTextArea().apply {
        isEditable = false
        lineWrap = false
        font = Font(Font.MONOSPACED, Font.PLAIN, 12)
        text = "Sergeant 0.3.0-preview\n\nReady to review ${project.name}."
    }
    private val runButton = JButton("Review Project")

    init {
        border = JBUI.Borders.empty(12)
        val header = JPanel(BorderLayout()).apply {
            border = JBUI.Borders.emptyBottom(10)
            add(JBLabel("Sergeant Command Center").apply {
                font = font.deriveFont(Font.BOLD, 16f)
            }, BorderLayout.NORTH)
            add(JBLabel("Evidence before opinion. Verification before release."), BorderLayout.CENTER)
            add(runButton, BorderLayout.SOUTH)
        }
        add(header, BorderLayout.NORTH)
        add(JBScrollPane(output), BorderLayout.CENTER)
        runButton.addActionListener { runReview() }
    }

    private fun runReview() {
        runButton.isEnabled = false
        output.text = "Running Sergeant review…"
        ApplicationManager.getApplication().executeOnPooledThread {
            val result = SergeantRunner.review(project)
            ApplicationManager.getApplication().invokeLater {
                output.text = "Exit code: ${result.exitCode}\n\n${result.output}"
                output.caretPosition = 0
                runButton.isEnabled = true
            }
        }
    }
}
