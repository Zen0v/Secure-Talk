# Author: Rodrigo Graca

import Constants
from Constants import DisplayCommands
from Server import Server
from Client import Client

import wx
import time
import threading
import sys, os


class SecureTalk(wx.Frame):
    def __init__(self, *args, **kw):
        # ensure the parent's __init__ is called
        super(SecureTalk, self).__init__(*args, **kw)

        if sys.platform == 'win32':
            # only do this on windows, so we don't
            # cause an error dialog on other platforms
            exeName = sys.executable
            icon = wx.Icon(exeName, wx.BITMAP_TYPE_ICO)
            self.SetIcon(icon)

        # create a panel in the frame
        self.pnl = wx.Panel(self)

        # Add all elements which are in the panel
        self.makePanelElements()

        # create a menu bar
        self.makeMenuBar()

        # and a status bar
        self.CreateStatusBar()
        self.SetStatusText("Welcome to Secure Talk! Communicate wirelessly without worry!")

        # Can be either Server or Client
        self.currentConnectionHandle: Client = None

        # How often the output is refreshed
        self.OUTPUT_REFRESH_RATE = Constants.OUTPUT_REFRESH_RATE

        # Small thread to independently update the output box
        self.updateOutputThread = threading.Thread(target=self.updateOutput, daemon=True)
        self.updateOutputThread.start()

        # What should be displayed as the user's name in 'output'
        self.identifier = "Me: "

    def makePanelElements(self):

        # Labels
        outputLabel = wx.StaticText(self.pnl, label="Chat", pos=(25, 3))
        inputLabel = wx.StaticText(self.pnl, label="User input", pos=(25, 348))

        font = outputLabel.GetFont()
        font.PointSize += 3
        outputLabel.SetFont(font)
        inputLabel.SetFont(font)

        # TextControl
        self.output = wx.TextCtrl(self.pnl, pos=(18, 25), size=(395, 300), style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.ClientInput = wx.TextCtrl(self.pnl, pos=(18, 370), size=(395, 22), style=wx.TE_PROCESS_ENTER)

        # Adjust the text size of the output
        font = self.output.GetFont()
        font.PointSize += 1
        self.output.SetFont(font)

        self.Bind(wx.EVT_TEXT_ENTER, self.OnEnter, self.ClientInput)

    def makeMenuBar(self):
        # Make a file menu with File and Exit items
        fileMenu = wx.Menu()

        # Add a call to send files
        fileItem = fileMenu.Append(-1, "&Send File...\tCtrl-F", "Send a file over this protocol")
        fileMenu.AppendSeparator()

        # Exit program and it's daemons
        exitItem = fileMenu.Append(wx.ID_EXIT)

        # Now a help menu for the about item
        helpMenu = wx.Menu()
        aboutItem = helpMenu.Append(wx.ID_ABOUT)

        # Connection Handler
        connectionMenu = wx.Menu()

        # Control and start connections
        serverItem = connectionMenu.Append(0, "&Server", "Act as the server and prepare for a connection")
        clientItem = connectionMenu.Append(1, "&Client", "Connect to a server at a given IP")
        closeItem = connectionMenu.Append(2, "&Close", "Close the current connection")

        # Apply all these menus to the bar
        menuBar = wx.MenuBar()
        menuBar.Append(fileMenu, "&File")
        menuBar.Append(helpMenu, "&Help")
        menuBar.Append(connectionMenu, "&Connections")

        # Give the menu bar to the frame
        self.SetMenuBar(menuBar)

        # Finally, associate a handler function with the EVT_MENU event for
        # each of the menu items. That means that when that menu item is
        # activated then the associated handler function will be called.
        self.Bind(wx.EVT_MENU, self.OnFileSend, fileItem)
        self.Bind(wx.EVT_MENU, self.OnExit, exitItem)
        self.Bind(wx.EVT_MENU, self.OnAbout, aboutItem)
        self.Bind(wx.EVT_MENU, self.OnServer, serverItem)
        self.Bind(wx.EVT_MENU, self.OnClient, clientItem)
        self.Bind(wx.EVT_MENU, self.onClose, closeItem)

    def OnFileSend(self, event):
        if self.currentConnectionHandle:
            if self.currentConnectionHandle.readyToTransmit:
                # TODO Add ability to send files

                openFile = wx.FileDialog(self, "Select file to send", ".", "", "*", wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)

                openFile.ShowModal()
                filePath = openFile.GetPath()
                print(filePath)
                openFile.Destroy()

                self.currentConnectionHandle.sendFile(filePath)
            else:
                wx.MessageBox("Connection not stabilized yet!", style=wx.ICON_INFORMATION)
        else:
            wx.MessageBox("You are not connected to anyone yet!", style=wx.ICON_INFORMATION)

    def OnExit(self, event):
        # Close the frame and terminate any connection

        self.closeConn()
        self.Close(True)

    def OnAbout(self, event):
        # Display an About dialog
        wx.MessageBox("This is the about dialog for Secure Talk",
                      "About Secure Talk",
                      wx.OK | wx.ICON_INFORMATION)

    def OnEnter(self, event):

        # Get the value of the input, store & display it, then clear to be ready for more input
        text = self.ClientInput.GetValue()

        if text != "":
            if self.currentConnectionHandle:
                self.currentConnectionHandle.addToDisplay(self.identifier + text)
                self.currentConnectionHandle.addToSend(text)

            else:
                wx.MessageBox("You are not connected to anyone yet!", style=wx.ICON_INFORMATION)

            self.ClientInput.Clear()

    def OnServer(self, event):
        # Start a new server handle if no handle is currently active, otherwise deny
        if not self.currentConnectionHandle:
            self.currentConnectionHandle = Server()
            self.currentConnectionHandle.start()
        else:
            wx.MessageBox("You're already trying/are connected to someone!", style=wx.ICON_INFORMATION)

    def OnClient(self, event):
        # Start a new client handle if no handle is currently active, otherwise deny
        if not self.currentConnectionHandle:
            # TODO Bug: When selecting cancel in dialog program continues
            serverIP = self.ask(message="Where would you like to connect to? Please enter the IP below ",
                                default_value="localhost", caption="Server IP")
            self.currentConnectionHandle = Client(server_addr=(serverIP, 65532))
            self.currentConnectionHandle.start()
        else:
            wx.MessageBox("You're already trying/are connected to someone!", style=wx.ICON_INFORMATION)

    def ask(self, parent=None, message='', default_value='', caption='Hello'):
        dlg = wx.TextEntryDialog(parent, message, value=default_value, caption=caption)
        dlg.ShowModal()
        result = dlg.GetValue()
        dlg.Destroy()
        return result

    def updateOutput(self):

        # TODO Just no, fix this
        while True:
            if self.currentConnectionHandle:

                if self.currentConnectionHandle.isRunning():
                    if self.currentConnectionHandle.getRecvTotal() > 0:
                        msg = self.currentConnectionHandle.nextToDisplay()

                        if msg == DisplayCommands.clearOutput:
                            self.output.Clear()
                        elif msg:
                            self.output.AppendText(str(msg) + "\n")
                else:
                    wx.MessageBox("Connection dissolved! Did the recipient abruptly exit?", style=wx.ICON_ERROR)
                    self.closeConn()

            time.sleep(self.OUTPUT_REFRESH_RATE)

    def onClose(self, event):
        if self.currentConnectionHandle:
            result = wx.MessageBox("Would you like to end the connection?", style=wx.OK | wx.CANCEL | wx.CANCEL_DEFAULT)

            # Result: 4 == OK
            if result == 4:
                self.closeConn()

    def closeConn(self):
        if self.currentConnectionHandle:
            self.currentConnectionHandle.exit()
        self.currentConnectionHandle = None
        self.output.Clear()
        self.ClientInput.Clear()


def startGUI():
    # Next, create an application object.
    app = wx.App()

    # Then a frame.
    frm = SecureTalk(None, title="Secure Talk", size=Constants.WINDOW_SIZE,
                     style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))

    # Show it.
    frm.Show()

    # Start the event loop.
    app.MainLoop()


if __name__ == "__main__":
    startGUI()
