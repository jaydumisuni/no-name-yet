package com.thetechguyds.sergeant

import com.intellij.openapi.project.Project
import java.nio.charset.StandardCharsets
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit

internal object SergeantRunner {
    data class Result(val exitCode: Int, val output: String)

    fun review(project: Project): Result {
        val root = project.basePath ?: return Result(2, "Sergeant could not resolve the current project path.")
        val configured = System.getenv("SERGEANT_CLI")?.trim().orEmpty()
        val command = if (configured.isNotEmpty()) {
            listOf(configured, "review", root, "--pretty")
        } else {
            listOf("sergeant", "review", root, "--pretty")
        }

        return try {
            val process = ProcessBuilder(command)
                .directory(java.io.File(root))
                .redirectErrorStream(true)
                .start()
            val outputFuture = CompletableFuture.supplyAsync {
                process.inputStream.readBytes().toString(StandardCharsets.UTF_8)
            }
            val finished = process.waitFor(5, TimeUnit.MINUTES)
            if (!finished) {
                process.destroyForcibly()
                outputFuture.cancel(true)
                Result(124, "Sergeant review timed out after five minutes.")
            } else {
                Result(process.exitValue(), outputFuture.get())
            }
        } catch (error: Exception) {
            Result(
                127,
                "Unable to start the Sergeant CLI. Install it with 'pipx install sergeant-reviewer' " +
                    "or set SERGEANT_CLI to the executable path.\n\n${error.message}"
            )
        }
    }
}
