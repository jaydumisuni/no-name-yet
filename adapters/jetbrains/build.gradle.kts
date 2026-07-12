plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.1.20"
    id("org.jetbrains.intellij.platform") version "2.16.0"
}

val pluginGroup: String by project
val pluginName: String by project
val pluginVersion: String by project
val platformVersion: String by project

group = pluginGroup
version = pluginVersion

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity(platformVersion)
        pluginVerifier()
        zipSigner()
    }
}

sourceSets {
    main {
        resources.srcDir("../../resources")
    }
}

kotlin {
    jvmToolchain(21)
}

intellijPlatform {
    pluginConfiguration {
        name = pluginName
        version = pluginVersion
        ideaVersion {
            sinceBuild = "252"
        }
        vendor {
            name = "THETECHGUY DIGITAL SOLUTIONS"
            email = "support@thetechguyds.com"
            url = "https://thetechguyds.com"
        }
    }
    publishing {
        token = providers.environmentVariable("JETBRAINS_MARKETPLACE_TOKEN")
        channels = listOf("preview")
    }
}

tasks {
    wrapper {
        gradleVersion = "9.0.0"
    }
}
