package com.thetechguyds.sergeant

import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VfsUtilCore
import java.io.File
import java.nio.charset.StandardCharsets
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit

internal object SergeantRunner {
    data class Result(
        val action: String,
        val title: String,
        val exitCode: Int,
        val output: String,
    )

    fun run(project: Project, action: String): Result {
        val root = project.basePath ?: return Result(action, titleFor(action), 2, "Sergeant could not resolve the current project path.")
        val args = argumentsFor(project, action, root)
            ?: return Result(action, titleFor(action), 2, "The selected Sergeant mission needs an active file or changed files.")
        val configured = System.getenv("SERGEANT_CLI")?.trim().orEmpty()
        val executable = if (configured.isNotEmpty()) configured else "sergeant"
        val command = listOf(executable) + args

        return try {
            val process = ProcessBuilder(command)
                .directory(File(root))
                .redirectErrorStream(true)
                .start()
            val outputFuture = CompletableFuture.supplyAsync {
                process.inputStream.readBytes().toString(StandardCharsets.UTF_8)
            }
            val finished = process.waitFor(10, TimeUnit.MINUTES)
            if (!finished) {
                process.destroyForcibly()
                outputFuture.cancel(true)
                Result(action, titleFor(action), 124, "Sergeant mission timed out after ten minutes.")
            } else {
                Result(action, titleFor(action), process.exitValue(), outputFuture.get())
            }
        } catch (error: Exception) {
            Result(
                action,
                titleFor(action),
                127,
                "Unable to start the Sergeant CLI. Install it with 'pipx install sergeant-reviewer' " +
                    "or set SERGEANT_CLI to the executable path.\n\n${error.message}",
            )
        }
    }

    fun review(project: Project): Result = run(project, "reviewWorkspace")

    private fun argumentsFor(project: Project, action: String, root: String): List<String>? = when (action) {
        "reviewWorkspace" -> listOf("review", root, "--pretty")
        "appReviewWorkspace" -> listOf("app-review", root, "--pretty")
        "reviewCurrentFile" -> activeFile(project, root)?.let {
            listOf("app-review", root, "--mode", "changed_files", "--files", it, "--pretty")
        }
        "reviewChangedFiles" -> changedFiles(root)?.let {
            listOf("app-review", root, "--mode", "changed_files", "--files", it, "--pretty")
        }
        "v2Mission" -> listOf("v2-mission", root, "--mission-type", "release_gate_review", "--pretty")
        "proofSuite" -> listOf("proof-suite", root, "--pretty")
        "finalProof" -> listOf("final-proof", root, "--pretty")
        "verifyStandard" -> listOf("verify-standard", root, "--pretty")
        "battleTests" -> listOf("battle-tests", root, "--pretty")
        "ideBenchContract" -> listOf("ide-bench-contract", "--pretty")
        else -> null
    }

    private fun activeFile(project: Project, root: String): String? {
        val file = FileEditorManager.getInstance(project).selectedFiles.firstOrNull() ?: return null
        return VfsUtilCore.getRelativePath(file, project.baseDir) ?: File(file.path).relativeToOrNull(File(root))?.path
    }

    private fun changedFiles(root: String): String? = try {
        val process = ProcessBuilder("git", "diff", "--name-only", "HEAD")
            .directory(File(root))
            .redirectErrorStream(true)
            .start()
        val output = process.inputStream.bufferedReader().readText()
        process.waitFor(20, TimeUnit.SECONDS)
        output.lineSequence().map(String::trim).filter(String::isNotEmpty).joinToString(",").ifBlank { null }
    } catch (_: Exception) {
        null
    }

    private fun titleFor(action: String): String = when (action) {
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
