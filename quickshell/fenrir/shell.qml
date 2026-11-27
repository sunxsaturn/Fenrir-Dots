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
    property bool launcherOpen: false
    property string launcherQuery: ""
    property string launcherCategory: "All"
    property string clockText: "--:--"
    property var applications: []
    property var filteredApplications: {
        const query = launcherQuery.trim().toLowerCase();
        return applications.filter(app => {
            const categoryMatch = launcherCategory === "All"
                || (launcherCategory === "Favorites" ? app.favorite
                    : app.categories.indexOf(launcherCategory) >= 0);
            return categoryMatch && (!query || app.search_text.indexOf(query) >= 0);
        }).slice(0, 300);
    }

    function openLauncher() {
        root.launcherOpen = true;
        root.launcherQuery = "";
        root.launcherCategory = "All";
        applicationsProcess.running = true;
    }

    function toggleLauncher() {
        if (root.launcherOpen)
            root.launcherOpen = false;
        else
            root.openLauncher();
    }

    function setApplications(source) {
        try {
            const parsed = JSON.parse(source);
            if (!Array.isArray(parsed))
                throw new Error("application index is not an array");
            root.applications = parsed;
        } catch (error) {
            console.warn("Fenrir launcher: could not load the XDG application index.", error);
            root.applications = [];
        }
    }

    function launchApplication(app) {
        if (!app || !app.desktop_id)
            return;
        launchAppProcess.desktopId = app.desktop_id;
        launchAppProcess.running = true;
        root.launcherOpen = false;
    }

    function toggleFavorite(app) {
        if (!app || !app.desktop_id)
            return;
        favoriteAppProcess.desktopId = app.desktop_id;
        favoriteAppProcess.running = true;
    }
    property var palette: ({
        background: "#090b12",
        surface: "#151a28",
        surfaceAlt: "#1d2434",
        foreground: "#edf0fa",
        muted: "#a8afc4",
        accent: "#8b5cf6",
        selectionForeground: "#ffffff"
    })

    function refreshTheme() {
        if (!themeFile.loaded)
            return;
        try {
            const values = JSON.parse(themeFile.text());
            const validHex = value => typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
            root.palette = {
                background: validHex(values.background) ? values.background : root.palette.background,
                surface: validHex(values.surface) ? values.surface : "#151a28",
                surfaceAlt: validHex(values.surface_alt) ? values.surface_alt : "#1d2434",
                foreground: validHex(values.foreground) ? values.foreground : root.palette.foreground,
                muted: validHex(values.muted) ? values.muted : root.palette.muted,
                accent: validHex(values.accent) ? values.accent : root.palette.accent,
                selectionForeground: validHex(values.selection_foreground)
                                     ? values.selection_foreground : root.palette.selectionForeground
            };
        } catch (error) {
            console.warn("Fenrir: invalid theme.json; keeping the last valid palette.", error);
        }
    }

    function tint(token, opacity) {
        const base = Qt.color(root.palette[token] || root.palette.background);
        return Qt.rgba(base.r, base.g, base.b, opacity);
    }

    FileView {
        id: themeFile
        path: (Quickshell.env("HOME") || "") + "/.config/fenrir/theme/theme.json"
        watchChanges: true
        printErrors: false
        onLoaded: root.refreshTheme()
        onFileChanged: reload()
    }

    IpcHandler {
        target: "fenrir"
        function toggleLauncher(): void { root.toggleLauncher(); }
        function openLauncher(): void { root.openLauncher(); }
        function closeLauncher(): void { root.launcherOpen = false; }
    }

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

    Process {
        id: applicationsProcess
        command: ["fenrir-applications", "list", "--json"]
        stdout: StdioCollector {
            onStreamFinished: root.setApplications(this.text)
        }
    }
    Process {
        id: launchAppProcess
        property string desktopId: ""
        command: ["gtk-launch", desktopId]
    }
    Process {
        id: favoriteAppProcess
        property string desktopId: ""
        command: ["fenrir-applications", "favorite", "toggle", desktopId]
        onExited: applicationsProcess.running = true
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
                    color: root.tint("background", 0.60)
                    border.width: 1
                    border.color: root.tint("foreground", 0.20)

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 14

                        Text {
                            text: "ᚠ  FENRIR"
                            color: root.palette.foreground
                            font.family: "Inter"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }

                        Rectangle {
                            width: 1
                            height: 20
                            color: root.tint("accent", 0.22)
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
                                           ? root.palette.accent : root.tint("surfaceAlt", 0.20)
                                    border.width: 1
                                    border.color: (Hyprland.focusedWorkspace && Hyprland.focusedWorkspace.id === index + 1)
                                                  ? root.palette.accent : root.tint("accent", 0.22)

                                    Text {
                                        anchors.centerIn: parent
                                        text: String(index + 1)
                                        color: root.palette.selectionForeground
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
                            color: root.tint("surfaceAlt", 0.13)
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
                            color: root.tint("accent", 0.22)
                        }

                        Text {
                            text: Pipewire.defaultAudioSink && Pipewire.defaultAudioSink.audio
                                  ? Math.round(Pipewire.defaultAudioSink.audio.volume * 100) + "%"
                                  : "AUDIO"
                            color: root.palette.muted
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Text {
                            text: root.clockText
                            color: root.palette.foreground
                            font.family: "Inter"
                            font.pixelSize: 12
                        }

                        Rectangle {
                            width: 34
                            height: 29
                            radius: 7
                            color: root.controlCenterOpen ? root.palette.accent : root.tint("surfaceAlt", 0.20)

                            Text {
                                anchors.centerIn: parent
                                text: notificationServer.trackedNotifications.count > 0
                                      ? "◉ " + notificationServer.trackedNotifications.count
                                      : "☰"
                                color: root.palette.selectionForeground
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
                    color: root.tint("background", 0.60)
                    border.width: 1
                    border.color: root.tint("foreground", 0.25)

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
                                color: root.tint("surfaceAlt", 0.14)
                                border.width: 1
                                border.color: root.tint("accent", 0.13)

                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: root.palette.foreground
                                    font.pixelSize: 20
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onEntered: parent.color = root.tint("accent", 0.30)
                                    onExited: parent.color = root.tint("surfaceAlt", 0.14)
                                    onClicked: {
                                        if (modelData.action === 0) root.openLauncher();
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
        color: root.palette.background

        Rectangle {
            anchors.fill: parent
            color: root.palette.background
            border.width: 1
            border.color: root.tint("accent", 0.40)
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
                            color: root.palette.foreground
                            font.family: "Inter"
                            font.pixelSize: 17
                            font.weight: Font.DemiBold
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: "SYSTEM CENTER"
                            color: root.palette.muted
                            font.family: "Inter"
                            font.pixelSize: 10
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Rectangle {
                            width: 30
                            height: 28
                            radius: 7
                            color: root.palette.surfaceAlt

                            Text {
                                anchors.centerIn: parent
                                text: "×"
                                color: root.palette.muted
                                font.pixelSize: 20
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.controlCenterOpen = false
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Text {
                        text: "APPEARANCE PROFILES"
                        color: root.palette.muted
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
                            color: root.tint("accent", 0.26)
                            border.color: root.palette.accent

                            Text {
                                anchors.centerIn: parent
                                text: "Norse Cinematic · 60%"
                                color: root.palette.selectionForeground
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
                            color: root.palette.surfaceAlt
                            border.color: root.tint("accent", 0.45)

                            Text {
                                anchors.centerIn: parent
                                text: "Norse Performance"
                                color: root.palette.foreground
                                font.pixelSize: 12
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: root.glassPerformanceProcess.running = true
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Row {
                        width: parent.width
                        Text {
                            text: "AUDIO"
                            color: root.palette.muted
                            font.family: "Inter"
                            font.pixelSize: 11
                        }
                        Item { width: 1; height: 1 }
                        Text {
                            text: Pipewire.defaultAudioSink
                                  ? Pipewire.defaultAudioSink.description
                                  : "No output device"
                            color: root.palette.muted
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
                            color: root.palette.foreground
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
                            color: root.palette.foreground
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

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Row {
                        width: parent.width

                        Text {
                            text: "MEDIA"
                            color: root.palette.muted
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: Mpris.players.count > 0 ? Mpris.players.count + " player(s)" : "No active player"
                            color: root.palette.muted
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
                            color: root.palette.surface
                            border.width: 1
                            border.color: root.tint("accent", 0.35)

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
                                        color: root.palette.foreground
                                        font.pixelSize: 12
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        width: parent.width
                                        text: (modelData.trackArtist || "Unknown artist") + " · " + modelData.identity
                                        color: root.palette.muted
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
                                        color: root.palette.surfaceAlt
                                        Text {
                                            anchors.centerIn: parent
                                            text: "◀"
                                            color: root.palette.foreground
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
                                        color: root.tint("accent", 0.65)
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.isPlaying ? "Ⅱ" : "▶"
                                            color: root.palette.selectionForeground
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
                                        color: root.palette.surfaceAlt
                                        Text {
                                            anchors.centerIn: parent
                                            text: "▶"
                                            color: root.palette.foreground
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

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Text {
                        text: "CONNECTIVITY"
                        color: root.palette.muted
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
                            color: root.palette.surfaceAlt
                            Text {
                                anchors.centerIn: parent
                                text: "Network settings"
                                color: root.palette.foreground
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
                            color: root.palette.surfaceAlt
                            Text {
                                anchors.centerIn: parent
                                text: "Audio patchbay"
                                color: root.palette.foreground
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
                            color: root.palette.muted
                            font.pixelSize: 10
                        }
                    }

                    Text {
                        text: Bluetooth.defaultAdapter
                              ? Bluetooth.defaultAdapter.name + (Bluetooth.defaultAdapter.enabled ? " · Bluetooth ready" : " · Bluetooth off")
                              : "No Bluetooth adapter detected"
                        color: root.palette.muted
                        font.pixelSize: 10
                    }

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Row {
                        width: parent.width

                        Text {
                            text: "OPEN WINDOWS"
                            color: root.palette.muted
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: Hyprland.toplevels.count + " window(s)"
                            color: root.palette.muted
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
                            color: modelData.activated ? root.tint("accent", 0.35) : root.palette.surface
                            border.width: 1
                            border.color: modelData.activated ? root.tint("accent", 0.55) : root.tint("accent", 0.35)

                            Text {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                verticalAlignment: Text.AlignVCenter
                                text: modelData.title || "Untitled window"
                                color: root.palette.foreground
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

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Row {
                        width: parent.width

                        Text {
                            text: "NOTIFICATIONS"
                            color: root.palette.muted
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Item { width: 1; height: 1 }

                        Text {
                            text: notificationServer.trackedNotifications.count + " stored"
                            color: root.palette.muted
                            font.pixelSize: 10
                        }

                        Rectangle {
                            width: 62
                            height: 26
                            radius: 7
                            color: root.tint("accent", 0.26)
                            Text {
                                anchors.centerIn: parent
                                text: "Clear all"
                                color: root.palette.selectionForeground
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
                            color: root.palette.surface
                            border.width: 1
                            border.color: modelData.urgency === 2 ? "#87505e" : root.tint("accent", 0.35)

                            Column {
                                anchors.fill: parent
                                anchors.margins: 11
                                spacing: 5

                                Row {
                                    width: parent.width

                                    Text {
                                        width: parent.width - 72
                                        text: modelData.appName || "Notification"
                                        color: root.palette.accent
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }

                                    Rectangle {
                                        width: 62
                                        height: 22
                                        radius: 6
                                        color: root.palette.surfaceAlt
                                        Text {
                                            anchors.centerIn: parent
                                            text: "Dismiss"
                                            color: root.palette.foreground
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
                                    color: root.palette.foreground
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.WordWrap
                                }

                                Text {
                                    id: notificationBody
                                    width: parent.width
                                    text: modelData.body || ""
                                    textFormat: Text.PlainText
                                    color: root.palette.muted
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    Rectangle { width: parent.width; height: 1; color: root.tint("accent", 0.35) }

                    Row {
                        width: parent.width
                        spacing: 8

                        Rectangle {
                            width: (parent.width - 8) / 2
                            height: 42
                            radius: 9
                            color: root.palette.surfaceAlt
                            Text {
                                anchors.centerIn: parent
                                text: "Next wallpaper"
                                color: root.palette.foreground
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
                            color: root.palette.surfaceAlt
                            Text {
                                anchors.centerIn: parent
                                text: "Fenrir Doctor"
                                color: root.palette.foreground
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
                        color: root.palette.muted
                        font.pixelSize: 10
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
    FloatingWindow {
        id: applicationLauncher
        visible: root.launcherOpen
        title: "Fenrir Application Launcher"
        width: 760
        height: 680
        color: root.palette.background
        onVisibleChanged: {
            if (visible) {
                if (root.applications.length === 0)
                    applicationsProcess.running = true;
                launcherSearch.forceActiveFocus();
            }
        }

        Rectangle {
            anchors.fill: parent
            color: root.palette.background
            border.width: 1
            border.color: root.tint("accent", 0.55)
            radius: 16

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                Row {
                    width: parent.width
                    spacing: 12

                    Column {
                        width: parent.width - 50
                        spacing: 3
                        Text {
                            text: "FENRIR"
                            color: root.palette.accent
                            font.family: "Inter"
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: "Application launcher"
                            color: root.palette.foreground
                            font.family: "Inter"
                            font.pixelSize: 22
                            font.weight: Font.DemiBold
                        }
                    }

                    Controls.Button {
                        text: "×"
                        onClicked: root.launcherOpen = false
                    }
                }

                Controls.TextField {
                    id: launcherSearch
                    width: parent.width
                    placeholderText: "Search applications, categories and descriptions…"
                    text: root.launcherQuery
                    onTextChanged: root.launcherQuery = text
                    onAccepted: {
                        if (root.filteredApplications.length > 0)
                            root.launchApplication(root.filteredApplications[0]);
                    }
                }

                Row {
                    width: parent.width
                    spacing: 10

                    Controls.ComboBox {
                        width: 190
                        model: ["All", "Favorites", "AudioVideo", "Development", "Game", "Graphics",
                                "Network", "Office", "Settings", "System", "Utility"]
                        currentIndex: Math.max(0, model.indexOf(root.launcherCategory))
                        onActivated: root.launcherCategory = currentText
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.filteredApplications.length + " applications"
                        color: root.palette.muted
                        font.pixelSize: 11
                    }

                    Item { width: 1; height: 1 }
                    Controls.Button {
                        text: "Refresh"
                        onClicked: applicationsProcess.running = true
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 1
                    color: root.tint("accent", 0.35)
                }

                ListView {
                    id: applicationList
                    width: parent.width
                    height: parent.height - 154
                    clip: true
                    spacing: 5
                    model: root.filteredApplications

                    delegate: Rectangle {
                        required property var modelData
                        width: applicationList.width
                        height: 64
                        radius: 10
                        color: root.tint("surface", 0.78)
                        border.width: 1
                        border.color: root.tint("accent", 0.16)

                        Row {
                            anchors.fill: parent
                            anchors.margins: 8
                            spacing: 10

                            Rectangle {
                                width: 46
                                height: 46
                                radius: 10
                                color: root.tint("accent", 0.25)
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.name.length ? modelData.name.charAt(0).toUpperCase() : "•"
                                    color: root.palette.foreground
                                    font.pixelSize: 20
                                    font.weight: Font.DemiBold
                                }
                            }

                            Controls.Button {
                                width: parent.width - 124
                                height: 46
                                anchors.verticalCenter: parent.verticalCenter
                                flat: true
                                onClicked: root.launchApplication(modelData)
                                background: Rectangle { color: "transparent" }
                                contentItem: Column {
                                    spacing: 3
                                    Text {
                                        text: modelData.name
                                        color: root.palette.foreground
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: modelData.comment || modelData.categories.join(" · ")
                                        color: root.palette.muted
                                        font.pixelSize: 10
                                        elide: Text.ElideRight
                                    }
                                }
                            }

                            Controls.Button {
                                width: 42
                                height: 42
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.favorite ? "★" : "☆"
                                onClicked: root.toggleFavorite(modelData)
                            }
                        }
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: root.filteredApplications.length === 0
                        text: root.applications.length === 0
                              ? "Loading installed applications…"
                              : "No applications match this search."
                        color: root.palette.muted
                        font.pixelSize: 12
                    }
                }

                Text {
                    width: parent.width
                    text: "Super + Space to toggle · Enter to launch · ☆ to save favorites"
                    color: root.palette.muted
                    font.pixelSize: 10
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

}
