package com.thetechguyds.sergeant

import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.ui.Messages

class ReviewProjectAction : AnAction() {
    override fun actionPerformed(event: AnActionEvent) {
        val project = event.project ?: return
        ApplicationManager.getApplication().executeOnPooledThread {
            val result = SergeantRunner.review(project)
            ApplicationManager.getApplication().invokeLater {
                if (project.isDisposed) return@invokeLater
                val title = if (result.exitCode == 0) "Sergeant Review" else "Sergeant Review Failed"
                val icon = if (result.exitCode == 0) Messages.getInformationIcon() else Messages.getErrorIcon()
                Messages.showMessageDialog(project, result.output, title, icon)
            }
        }
    }

    override fun update(event: AnActionEvent) {
        event.presentation.isEnabledAndVisible = event.project != null
    }
}
