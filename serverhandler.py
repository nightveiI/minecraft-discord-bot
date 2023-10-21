import os
import socket
import subprocess
import time
import mcrcon #pip install mcrcon

# server_run_command = "java -Xmx3G -Xms3G -jar server.jar nogui"
server_run_command = "java -Xmx3G -Xms3G -jar server.jar nogui"
filename = '/home/ec2-user/minecraft-server/server.properties'

def getServerProperties():
    server_properties = dict()
    with open(filename, "r") as fi:
        for line in fi.readlines():
            if line[0] == "#":  # comment only line
                continue
            try:
                definition = line.split("#")[0].split("=")  # remove comments from the .properties file, then split it into (parameter, value)
                server_properties[definition[0].strip()] = definition[1].strip()
            except IndexError:
                print(f"Couldn't do line: {line}")

    for k, v in server_properties.items():
        # bools
        if v.upper() == "TRUE":
            server_properties[k] = True
        elif v.upper() == "FALSE":
            server_properties[k] = False
        else:
            # try and convert to an int
            try:
                server_properties[k] = int(v)
            except ValueError:
                pass

    return server_properties


class ServerHandlerCommandFailure(Exception):
    def __init__(self, message):
        super().__init__(f"Server Handler failed to send a message: {message}")
        self.message = message


class ServerHandler(object):
    def __init__(self):
        self.subprocess = None
        self.service_start_time = None
        self.serverProperties = None

    def _closeNice(self):
        """
        :return: True if it closed nicely, false otherwise.
        """
        if self.subprocess is None:
            return True
        # self.subprocess.communicate('/say Server is shutting down now!\n'.encode())
        self.subprocess.communicate('/stop\n'.encode())
        time.sleep(1)
        # self.subprocess.communicate('/stop\n'.encode())
        for wait_cycles in range(30):
            if self.subprocess.poll() is not None:
                self.subprocess = None
                return True
            time.sleep(1)
        print("Subprocess seems to still be running.")
        return False

    def _terminate(self):
        """
        should always use _closeNice() in the first instance
        """
        self.subprocess.kill()

    def start(self):
        if self.subprocess is not None:
            return 1
        self.serverProperties = getServerProperties()
        #initialise the subprocess to execute in another directory
        self.subprocess = subprocess.Popen(server_run_command, cwd="/home/ec2-user/minecraft-server", stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        self.service_start_time = time.time()
        return 0

    def stop(self):
        if self._closeNice():
            return 0
        self._terminate()
        return 1

    def uptimeAsString(self):
        if self.subprocess is None or self.service_start_time is None:  # should only ever be stopped by the first conditional
            return "(server process isn't running)"
        return time.strftime("%b %d %Y %H:%M:%S", time.gmtime(self.service_start_time))

    def sendRcon(self, command_string):
        if self.subprocess is None:
            raise ServerHandlerCommandFailure("Server is not running.")
        if self.serverProperties["enable-rcon"] is False:
            raise ServerHandlerCommandFailure("RCON is not enabled.")
        try:
            with mcrcon.MCRcon(self.serverProperties["rcon.password"], "localhost", self.serverProperties["rcon.port"]) as mcr:
                resp = mcr.command(command_string)
                return resp
        except socket.error:
            raise ServerHandlerCommandFailure("RCON is not enabled.")