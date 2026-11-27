import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Services.Mpris
import Quickshell.Services.Notifications
import Quickshell.Services.Pipewire
import Quickshell.Services.SystemTray
import Quickshell.Networking
import Quickshell.Bluetooth
import QtQuick
import QtQuick.Controls as Controls

Scope {
    id: root

    property bool controlCenterOpen: false
    property string clockText: "--:--"

    NotificationServer {
        id: notificationServer
        actionsSupported: true
        persistenceSupported: true
        keepOnReload: true
        onNotification: notification => notification.tracked = true
    }

    PwObjectTracker {
        objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource]
    }

    Process {
        id: clockProcess
        command: ["date", "+%a %d %b  %H:%M"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: root.clockText = this.text.trim()
        }
    }

    Timer {
        interval: 15000
        running: true
        repeat: true
        onTriggered: clockProcess.running = true
    }

    Process { id: launcherProcess; command: ["fuzzel"] }
    Process { id: terminalProcess; command: ["kitty"] }
    Process { id: filesProcess; command: ["thunar"] }
    Process { id: browserProcess; command: ["firefox"] }
    Process { id: musicProcess; command: ["flatpak", "run", "com.spotify.Client"] }
    Process { id: audioProcess; command: ["qpwgraph"] }
    Process { id: doctorProcess; command: ["fenrir-doctor"] }
    Process { id: wallpaperProcess; command: ["fenrir-wallpaper", "next"] }
    Process { id: networkEditorProcess; command: ["nm-connection-editor"] }
    Process { id: glassCinematicProcess; command: ["fenrir-glass", "enable", "--opacity", "0.60"] }
    Process { id: glassPerformanceProcess; command: ["fenrir-glass", "disable"] }

    Variants {
        model: Quickshell.screens

        delegate: Component {
            PanelWindow {
                required property var modelData
                screen: modelData
                anchors {
                    top: true
                    left: true
                    right: true
                }
                implicitHeight: 46
                color: "transparent"
                WlrLayershell.namespace: "fenrir-top"

                Rectangle {
                    anchors.fill: parent
                    color: "#99090b12"
                    border.width: 1
                    border.color: "#33ffffff"

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 14

                        Text {
                            text: "ᚠ  FENRIR"
                            color: "#edf0fa"
                            font.family: "Inter"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Rectangle {
                            width: 1
                            height: 20
                            color: "#334a526b"
                        }

                        Row {
                            spacing: 5
                            Repeater {
                                model: 5
                                delegate: Rectangle {
                                    required property int index
                                    width: 28
                                    height: 27
                                    radius: 7
                                    color: (Hyprland.focusedWorkspace && Hyprland.focusedWorkspace.id === index + 1)
                                           ? "#8b5cf6" : "#331e293b"
                                    border.width: 1
                                    border.color: (Hyprland.focusedWorkspace && Hyprland.focusedWorkspace.id === index + 1)
                                                  ? "#bba7ff" : "#334a526b"

                                    Text {
                                        anchors.centerIn: parent
                                        text: String(index + 1)
                                        color: "#f4f2ff"
                                        font.family: "JetBrainsMono Nerd Font"
                                        font.pixelSize: 12
                                    }

                                    Process {
                                        id: workspaceProcess
                                        command: ["hyprctl", "dispatch", "workspace", String(index + 1)]
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: workspaceProcess.running = true
                                    }
                                }
                            }
                        }
                    }

                    Row {
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 8

                        Rectangle {
                            width: 170
                            height: 30
                            radius: 8
                            color: "#221e293b"
                            clip: true

                            Row {
                                anchors.centerIn: parent
                                spacing: 7

                                Repeater {
                                    model: SystemTray.items
                                    delegate: Item {
                                        required property var modelData
                                        width: 22
                                        height: 24

                                        Image {
                                            anchors.centerIn: parent
                                            width: 18
                                            height: 18
                                            source: modelData.icon
                                            fillMode: Image.PreserveAspectFit
                                            smooth: true
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                                            onClicked: mouse => {
                                                if (mouse.button === Qt.MiddleButton)
                                                    modelData.secondaryActivate();
                                                else
                                                    modelData.activate();
                                            }
                                            onPressAndHold: modelData.secondaryActivate()
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            width: 1
                            height: 20
                            color: "#334a526b"
                        }

                        Text {
                            text: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio
                                  ? Math.round(Pipewire.defaultAudioSink.audio.volume * 100) + "%"
                                  : "AUDIO"
                            color: "#a8afc4"
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Text {
                            text: root.clockText
                            color: "#edf0fa"
                            font.family: "Inter"
                            font.pixelSize: 12
                        }

                        Rectangle {
                            width: 34
                            height: 29
                            radius: 7
                            color: root.controlCenterOpen ? "#8b5cf6" : "#331e293b"

                            Text {
                                anchors.centerIn: parent
                                text: notificationServer.trackedNotifications.count > 0
                                      ? "◉ " + notificationServer.trackedNotifications.count
                                      : "☰"
                                color: "#f4f2ff"
                                font.pixelSize: 13
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.controlCenterOpen = !root.controlCenterOpen
                            }
                        }
                    }
                }
            }
        }
    }

    Variants {
        model: Quickshell.screens

        delegate: Component {
            PanelWindow {
                required property var modelData
                screen: modelData
                anchors {
                    bottom: true
                    left: true
                    right: true
                }
                implicitHeight: 76
                color: "transparent"
                WlrLayershell.namespace: "fenrir-dock"

                Rectangle {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 12
                    width: 390
                    height: 56
                    radius: 17
                    color: "#99090b12"
                    border.width: 1
                    border.color: "#40ffffff"

                    Row {
                        anchors.centerIn: parent
                        spacing: 8

                        Repeater {
                            model: [
                                { label: "⌘", action: 0 },
                                { label: "▣", action: 1 },
                                { label: "◫", action: 2 },
                                { label: "◎", action: 3 },
                                { label: "♫", action: 4 },
                                { label: "◉", action: 5 }
                            ]

                            delegate: Rectangle {
                                required property var modelData
                                width: 43
                                height: 42
                                radius: 11
                                color: "#241e293b"
                                border.width: 1
                                border.color: "#223b4259"

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: "#e7e9f3"
                                    font.pixelSize: 20
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: parent.color = "#553b3157"
                                    onExited: parent.color = "#241e293b"
                                    onClicked: {
                                        if (modelData.action === 0) root.launcherProcess.running = true;
                                        else if (modelData.action === 1) root.terminalProcess.running = true;
                                        else if (modelData.action === 2) root.filesProcess.running = true;
                                        else if (modelData.action === 3) root.browserProcess.running = true;
                                        else if (modelData.action === 4) root.musicProcess.running = true;
                                        else if (modelData.action === 5) root.audioProcess.running = true;
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    FloatingWindow {
        visible: root.controlCenterOpen
        title: "Fenrir Control Center"
        width: 570
        height: 760
        color: "#090b12"

        Rectangle {
            anchors.fill: parent
            color: "#090b12"
            border.width: 1
            border.color: "#665c4b85"
            radius: 16

            ScrollView {
                anchors.fill: parent
                anchors.margins: 20
                clip: true

                Column {
                    width: parent.width
                    spacing: 14

                    Row {
                        width: parent.width
                        spacing: 12

                        Text {
                            text: "FIMBULWINTER"
                            color: "#edf0fa"
                            font.family: "Inter"
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: "SYSTEM CENTER"
                            color: "#777f98"
                            font.family: "Inter"
                            font.pixelSize: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Rectangle {
                            width: 30
                            height: 28
                            radius: 7
                            color: "#1a2230"

                            Text {
                                anchors.centerIn: parent
                                text: "×"
                                color: "#a8afc4"
                                font.pixelSize: 20
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.controlCenterOpen = false
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Text {
                        text: "APPEARANCE PROFILES"
                        color: "#a8afc4"
                        font.family: "Inter"
                        font.pixelSize: 11
                    }

                    Row {
                        width: parent.width
                        spacing: 8

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 46
                            radius: 10
                            color: "#31234a"
                            border.color: "#8b5cf6"

                            Text {
                                anchors.centerIn: parent
                                text: "Norse Cinematic · 60%"
                                color: "#f4f2ff"
                                font.pixelSize: 12
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.glassCinematicProcess.running = true
                            }
                        }

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 46
                            radius: 10
                            color: "#1a2230"
                            border.color: "#46546a"

                            Text {
                                anchors.centerIn: parent
                                text: "Norse Performance"
                                color: "#edf0fa"
                                font.pixelSize: 12
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.glassPerformanceProcess.running = true
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Row {
                        width: parent.width
                        Text {
                            text: "AUDIO"
                            color: "#a8afc4"
                            font.family: "Inter"
                            font.pixelSize: 11
                        }
                        Item { width: 1; height: 1 }
                        Text {
                            text: Pipewire.defaultAudioSink
                                  ? Pipewire.defaultAudioSink.description
                                  : "No output device"
                            color: "#8e9ab4"
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            width: 260
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 10

                        Text {
                            width: 70
                            text: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio
                                  ? (Pipewire.defaultAudioSink.audio.muted ? "Muted" : "Output")
                                  : "Output"
                            color: "#edf0fa"
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Controls.Slider {
                            id: outputVolume
                            width: parent.width - 140
                            from: 0
                            to: 1.5
                            value: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio
                                   ? Pipewire.defaultAudioSink.audio.volume : 0
                            enabled: !!(Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio)
                            onMoved: {
                                if (Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio)
                                    Pipewire.defaultAudioSink.audio.volume = value;
                            }
                        }

                        Text {
                            width: 60
                            text: Math.round(outputVolume.value * 100) + "%"
                            color: "#c5cbe0"
                            font.family: "JetBrainsMono Nerd Font"
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                            horizontalAlignment: Text.AlignRight
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 12

                        Controls.Switch {
                            text: "Mute output"
                            checked: !!(Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio
                                        && Pipewire.defaultAudioSink.audio.muted)
                            enabled: !!(Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio)
                            onToggled: {
                                if (Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio)
                                    Pipewire.defaultAudioSink.audio.muted = checked;
                            }
                        }

                        Controls.Switch {
                            text: "Mute microphone"
                            checked: !!(Pipewire.defaultAudioSource && Pipewire.defaultAudioSource.audio
                                        && Pipewire.defaultAudioSource.audio.muted)
                            enabled: !!(Pipewire.defaultAudioSource && Pipewire.defaultAudioSource.audio)
                            onToggled: {
                                if (Pipewire.defaultAudioSource && Pipewire.defaultAudioSource.audio)
                                    Pipewire.defaultAudioSource.audio.muted = checked;
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Row {
                        width: parent.width

                        Text {
                            text: "MEDIA"
                            color: "#a8afc4"
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: Mpris.players.count > 0 ? Mpris.players.count + " player(s)" : "No active player"
                            color: "#8e9ab4"
                            font.pixelSize: 10
                        }
                    }

                    Repeater {
                        model: Mpris.players

                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            height: 82
                            radius: 10
                            color: "#141b29"
                            border.width: 1
                            border.color: "#293244"

                            Row {
                                anchors.fill: parent
                                anchors.margins: 10
                                spacing: 12

                                Image {
                                    width: 58
                                    height: 58
                                    source: modelData.trackArtUrl
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    visible: modelData.trackArtUrl !== ""
                                }

                                Column {
                                    width: parent.width - 164
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 5

                                    Text {
                                        width: parent.width
                                        text: modelData.trackTitle || modelData.identity || "Unknown track"
                                        color: "#edf0fa"
                                        font.pixelSize: 12
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        width: parent.width
                                        text: (modelData.trackArtist || "Unknown artist") + " · " + modelData.identity
                                        color: "#8e9ab4"
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                }

                                Row {
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4

                                    Rectangle {
                                        width: 30
                                        height: 30
                                        radius: 7
                                        color: "#222c40"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "◀"
                                            color: "#edf0fa"
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: if (modelData.canGoPrevious) modelData.previous()
                                        }
                                    }

                                    Rectangle {
                                        width: 34
                                        height: 34
                                        radius: 8
                                        color: "#523b79"
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.isPlaying ? "Ⅱ" : "▶"
                                            color: "#ffffff"
                                            font.pixelSize: 15
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: if (modelData.canTogglePlaying) modelData.togglePlaying()
                                        }
                                    }

                                    Rectangle {
                                        width: 30
                                        height: 30
                                        radius: 7
                                        color: "#222c40"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "▶"
                                            color: "#edf0fa"
                                            font.pixelSize: 12
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: if (modelData.canGoNext) modelData.next()
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Text {
                        text: "CONNECTIVITY"
                        color: "#a8afc4"
                        font.family: "Inter"
                        font.pixelSize: 11
                    }

                    Row {
                        width: parent.width
                        spacing: 18

                        Controls.Switch {
                            text: "Wi-Fi"
                            checked: Networking.wifiEnabled
                            enabled: Networking.wifiHardwareEnabled
                            onToggled: Networking.wifiEnabled = checked
                        }

                        Controls.Switch {
                            text: "Bluetooth"
                            checked: !!(Bluetooth.defaultAdapter && Bluetooth.defaultAdapter.enabled)
                            enabled: !!Bluetooth.defaultAdapter
                            onToggled: {
                                if (Bluetooth.defaultAdapter)
                                    Bluetooth.defaultAdapter.enabled = checked;
                            }
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 8

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 38
                            radius: 8
                            color: "#1a2230"
                            Text {
                                anchors.centerIn: parent
                                text: "Network settings"
                                color: "#edf0fa"
                                font.pixelSize: 11
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.networkEditorProcess.running = true
                            }
                        }

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 38
                            radius: 8
                            color: "#1a2230"
                            Text {
                                anchors.centerIn: parent
                                text: "Audio patchbay"
                                color: "#edf0fa"
                                font.pixelSize: 11
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.audioProcess.running = true
                            }
                        }
                    }

                    Repeater {
                        model: Networking.devices
                        delegate: Text {
                            required property var modelData
                            width: parent.width
                            text: modelData.name + (modelData.connected ? " · Connected" : " · Disconnected")
                            color: "#8e9ab4"
                            font.pixelSize: 10
                        }
                    }

                    Text {
                        text: Bluetooth.defaultAdapter
                              ? Bluetooth.defaultAdapter.name + (Bluetooth.defaultAdapter.enabled ? " · Bluetooth ready" : " · Bluetooth off")
                              : "No Bluetooth adapter detected"
                        color: "#8e9ab4"
                        font.pixelSize: 10
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Row {
                        width: parent.width

                        Text {
                            text: "OPEN WINDOWS"
                            color: "#a8afc4"
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: Hyprland.toplevels.count + " window(s)"
                            color: "#8e9ab4"
                            font.pixelSize: 10
                        }
                    }

                    Repeater {
                        model: Hyprland.toplevels

                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            height: 38
                            radius: 8
                            color: modelData.activated ? "#302848" : "#141b29"
                            border.width: 1
                            border.color: modelData.activated ? "#665c91" : "#293244"

                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                verticalAlignment: Text.AlignVCenter
                                text: modelData.title || "Untitled window"
                                color: "#edf0fa"
                                font.pixelSize: 11
                                elide: Text.ElideRight
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    Hyprland.dispatch("focuswindow address:" + modelData.address);
                                    root.controlCenterOpen = false;
                                }
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Row {
                        width: parent.width

                        Text {
                            text: "NOTIFICATIONS"
                            color: "#a8afc4"
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: notificationServer.trackedNotifications.count + " stored"
                            color: "#8e9ab4"
                            font.pixelSize: 10
                        }

                        Rectangle {
                            width: 62
                            height: 26
                            radius: 7
                            color: "#31234a"
                            Text {
                                anchors.centerIn: parent
                                text: "Clear all"
                                color: "#f4f2ff"
                                font.pixelSize: 10
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    for (let i = notificationServer.trackedNotifications.count - 1; i >= 0; --i)
                                        notificationServer.trackedNotifications.get(i).dismiss();
                                }
                            }
                        }
                    }

                    Repeater {
                        model: notificationServer.trackedNotifications

                        delegate: Rectangle {
                            required property var modelData
                            width: parent.width
                            height: notificationBody.implicitHeight + 54
                            radius: 9
                            color: "#141b29"
                            border.width: 1
                            border.color: modelData.urgency === 2 ? "#87505e" : "#293244"

                            Column {
                                anchors.fill: parent
                                anchors.margins: 11
                                spacing: 5

                                Row {
                                    width: parent.width

                                    Text {
                                        width: parent.width - 72
                                        text: modelData.appName || "Notification"
                                        color: "#9b87f5"
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        width: 62
                                        height: 22
                                        radius: 6
                                        color: "#222c40"
                                        Text {
                                            anchors.centerIn: parent
                                            text: "Dismiss"
                                            color: "#c5cbe0"
                                            font.pixelSize: 9
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: modelData.dismiss()
                                        }
                                    }
                                }

                                Text {
                                    text: modelData.summary || "Notification"
                                    color: "#edf0fa"
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                }

                                Text {
                                    id: notificationBody
                                    width: parent.width
                                    text: modelData.body || ""
                                    textFormat: Text.PlainText
                                    color: "#a8afc4"
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: "#293244" }

                    Row {
                        width: parent.width
                        spacing: 8

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 42
                            radius: 9
                            color: "#1a2230"
                            Text {
                                anchors.centerIn: parent
                                text: "Next wallpaper"
                                color: "#edf0fa"
                                font.pixelSize: 11
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.wallpaperProcess.running = true
                            }
                        }

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 42
                            radius: 9
                            color: "#1a2230"
                            Text {
                                anchors.centerIn: parent
                                text: "Fenrir Doctor"
                                color: "#edf0fa"
                                font.pixelSize: 11
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.doctorProcess.running = true
                            }
                        }
                    }

                    Text {
                        width: parent.width
                        text: "Hyprland · Quickshell · PipeWire · NetworkManager · BlueZ"
                        color: "#707d96"
                        font.pixelSize: 10
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
}
