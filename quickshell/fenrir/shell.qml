import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import QtQuick

Scope {
    id: root

    property bool controlCenterOpen: false
    property string clockText: "--:--"

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
                        spacing: 10

                        Text {
                            text: "AUDIO"
                            color: "#a8afc4"
                            font.family: "Inter"
                            font.pixelSize: 11
                        }

                        Rectangle {
                            width: 1
                            height: 20
                            color: "#334a526b"
                        }

                        Text {
                            text: root.clockText
                            color: "#edf0fa"
                            font.family: "Inter"
                            font.pixelSize: 12
                        }

                        Rectangle {
                            width: 30
                            height: 28
                            radius: 7
                            color: root.controlCenterOpen ? "#8b5cf6" : "#331e293b"
                            Text {
                                anchors.centerIn: parent
                                text: "☰"
                                color: "#f4f2ff"
                                font.pixelSize: 16
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
        width: 380
        height: 490
        color: "#090b12"

        Rectangle {
            anchors.fill: parent
            color: "#090b12"
            border.width: 1
            border.color: "#665c4b85"
            radius: 16

            Column {
                anchors.fill: parent
                anchors.margins: 22
                spacing: 14

                Row {
                    width: parent.width
                    Text {
                        text: "FIMBULWINTER"
                        color: "#edf0fa"
                        font.family: "Inter"
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                    }
                    Item { width: 1; height: 1 }
                    Rectangle {
                        width: 28
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

                Text {
                    text: "Appearance profiles"
                    color: "#a8afc4"
                    font.family: "Inter"
                    font.pixelSize: 12
                }

                Row {
                    spacing: 8
                    Rectangle {
                        width: 156
                        height: 48
                        radius: 10
                        color: "#31234a"
                        border.color: "#8b5cf6"
                        Text {
                            anchors.centerIn: parent
                            text: "Norse Cinematic"
                            color: "#f4f2ff"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.glassCinematicProcess.running = true
                        }
                    }
                    Rectangle {
                        width: 156
                        height: 48
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

                Text {
                    text: "Desktop actions"
                    color: "#a8afc4"
                    font.family: "Inter"
                    font.pixelSize: 12
                }

                Row {
                    spacing: 8
                    Rectangle {
                        width: 156
                        height: 44
                        radius: 9
                        color: "#1a2230"
                        Text {
                            anchors.centerIn: parent
                            text: "Next wallpaper"
                            color: "#edf0fa"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.wallpaperProcess.running = true
                        }
                    }
                    Rectangle {
                        width: 156
                        height: 44
                        radius: 9
                        color: "#1a2230"
                        Text {
                            anchors.centerIn: parent
                            text: "Fenrir Doctor"
                            color: "#edf0fa"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.doctorProcess.running = true
                        }
                    }
                }

                Rectangle { width: parent.width; height: 1; color: "#293244" }

                Text {
                    text: "System services"
                    color: "#a8afc4"
                    font.family: "Inter"
                    font.pixelSize: 12
                }

                Text {
                    text: "Hyprland  ·  Quickshell  ·  PipeWire"
                    color: "#edf0fa"
                    font.family: "Inter"
                    font.pixelSize: 13
                }

                Text {
                    text: "Fimbulwinter Glass: 60% opacity in Cinematic profile"
                    color: "#98a3b9"
                    font.family: "Inter"
                    font.pixelSize: 11
                    wrapMode: Text.WordWrap
                    width: parent.width
                }
            }
        }
    }
}
