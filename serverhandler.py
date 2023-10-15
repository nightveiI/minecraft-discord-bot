import os
import socket
import subprocess
import time
import mcrcon #pip install mcrcon

# server_run_command = "java -Xmx5G -Xms5G -jar server.jar nogui"
server_run_command = "java -Xmx5G -Xms5G -jar server.jar nogui"
filename = os.path.dirname(os.path.realpath(__file__)) + '/../minecraft_server/server.properties'

def getServerProperties(filename):
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
        self.serverProperties = dict()

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
        self.subprocess = subprocess.Popen(server_run_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        self.service_start_time = time.time()
        self.serverProperties = getServerProperties()

    def stop(self):
        if not self._closeNice():
            self._terminate()

    def uptimeAsString(self):
        if self.subprocess is None or self.service_start_time is None:  # should only ever be stopped by the first conditional
            return "(server process isn't running)"
        return time.strftime("%b %d %Y %H:%M:%S", time.gmtime(self.service_start_time))

    def sendRcon(self, command_string):
        """
        Rcon socket is only open for the duration of this method.
        :param command_string:
        :return:
        """
        if self.subprocess is None:
            return 1
        try:
            with mcrcon.MCRcon("127.0.0.1", self.serverProperties["rcon.password"]) as mcr:
                mcr.command(command_string)
        except Exception as e:
            print(e)
            raise ServerHandlerCommandFailure(command_string)
        return 0


