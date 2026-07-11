plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.0.21"
    id("org.jetbrains.intellij.platform") version "2.2.1"
}

group = "com.thetechguyds.sergeant"
version = "0.3.0-preview"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2024.3")
        pluginVerifier()
        zipSigner()
    }
}

kotlin {
    jvmToolchain(21)
}

intellijPlatform {
    pluginConfiguration {
        name = "Sergeant"
        version = "0.3.0-preview"
        ideaVersion {
            sinceBuild = "243"
        }
        vendor {
            name = "THETECHGUY DIGITAL SOLUTIONS"
            email = "support@thetechguyds.com"
            url = "https://thetechguyds.com"
        }
    }
    publishing {
        token = providers.environmentVariable("JETBRAINS_MARKETPLACE_TOKEN")
        channels = listOf("eap")
    }
}

tasks {
    wrapper {
        gradleVersion = "8.10.2"
    }
}
