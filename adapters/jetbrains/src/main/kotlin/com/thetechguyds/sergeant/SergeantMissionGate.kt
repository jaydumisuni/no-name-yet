package com.thetechguyds.sergeant

import com.intellij.openapi.project.Project
import java.util.concurrent.ConcurrentHashMap

internal object SergeantMissionGate {
    private val activeProjects = ConcurrentHashMap.newKeySet<Project>()

    fun tryAcquire(project: Project): Boolean = activeProjects.add(project)

    fun release(project: Project) {
        activeProjects.remove(project)
    }

    fun isActive(project: Project): Boolean = activeProjects.contains(project)
}
