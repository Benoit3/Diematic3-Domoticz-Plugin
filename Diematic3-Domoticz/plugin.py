# Diematic3 Domoticz Plugin
#
# Author: Benoit3
#
"""
<plugin key="Diematic3" name="Diematic3 Plugin" author="Benoit3" version="0.0.1" wikilink="http://www.domoticz.com/wiki/plugins/plugin.html" externallink="https://www.google.com/">
    <description>
        <h2>Diematic3 </h2><br/>
        This plugin allows to connect and control a De Dietrich heater managed by a Diematic3 regulator
        <h3>Features</h3>
        <ul style="list-style-type:square">
            <li>Display of heater parameters</li>
            <li>Display and change various heater settings</li>
        </ul>
        <h3>Devices</h3>
        <ul style="list-style-type:square">
            <li>Device Type - What it does...</li>
        </ul>
        <h3>Configuration</h3>
        This plugin connects to the heater trough an athernet RS485 interface. it should be configured with the IP address of the interface
    </description>
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default="192.168.1.X"/>
        <param field="Port" label="Port" width="40px" required="true" default="20108"/>
        <param field="Mode6" label="Debug" width="100px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz,time
import ModBusDD

class BasePlugin:
    
    #specific diematic 3 register address
    __DIEM3_BASE_ECS=427
    __DIEM3_OPTIONS_BC=428
    __DIEM3_FAN_SPEED=455
        
    #Diematic3 float conversion function
    def diem3Float(data,bit):
        if data==0xFFFF:
            return "--"
        elif data >0x8000:
            return str(-(data&0x7FFF)/10.0)
        else:
            return str((data&0x7FFF)/10.0)
            
    #Diematic3 bit extraction function
    def diem3Bit(data,bit):
        mask=1<<bit
        return str((data&mask)>>bit)

    #Diematic3 alarm labels
    __ALARM_LABELS={0:"OK",
        10:"Défaut Sonde Retour",
        21:"Pression d'eau basse",
        26:"Défaut Allumage",
        28:"STB Chaudière",
        30:"Réarm. Coffret",
        31:"Défaut Sonde Fumée" 
        }
    #Diematic3 alarm label conversion function
    def diem3AlarmLabel(data,bit):
        if data in BasePlugin.__ALARM_LABELS:
            return BasePlugin.__ALARM_LABELS[data]
        else:
            return str(data)
    
    #Diematic3 mode labels
    __MODE_LABELS={8:"AUTO",
        0x04:"JOUR PERM",
        0x24:"JOUR TEMP",
        0x02:"NUIT PERM",
        0x22:"NUIT TEMP",
        0x01:"ANTIGEL PERM",
        0x21:"ANTIGEL TEMP" 
        }
    #Diematic3 alarm label conversion function
    def diem3ModeLabel(data,bit):
        data&=0x2F
        if data in BasePlugin.__MODE_LABELS:
            return BasePlugin.__MODE_LABELS[data]
        else:
            return str(data) 
    
    #Diematic3 ECS mode labels
    __ECS_MODE_LABELS={8:"AUTO",
        0x00:"AUTO",
        0x10:"PERM",
        0x50:"TEMP"
        }
        
    #Diematic3 alarm label conversion function
    def diem3EcsModeLabel(data,bit):
        data&=0x50
        if data in BasePlugin.__ECS_MODE_LABELS:
            return BasePlugin.__ECS_MODE_LABELS[data]
        else:
            return str(data) 
            
    #Diematic3 burner power
    __FAN_SPEED_MIN=1000
    __FAN_SPEED_MAX=6000

    #Diematic3 alarm label conversion function
    def diem3BurnerPower(data,bit):
        if data > BasePlugin.__FAN_SPEED_MIN:
            return str(10*round ((data / BasePlugin.__FAN_SPEED_MAX)*10,0));
        else:
            return "0"
            
    #Diematic3 day labels
    __DAY_LABELS={1:'Lundi',2:'Mardi',3:'Mercredi',4:'Jeudi',5:'Vendredi',6:'Samedi',7:'Dimanche'}
    
    #Diematic3 status labels
    __STATUS_LABELS={0:'Veille',1:'Chauffage',2:'Chauffe-Eau'}

    
    # Device units
    __UNIT_TYPE = 1
    __UNIT_CTRL = 2
    __UNIT_TEMPINTA = 3
    __UNIT_TEMPINTB = 4
    __UNIT_TEMPEXT = 5
    __UNIT_TEMPECS = 6
    __UNIT_PUMPA = 7
    __UNIT_PUMPB = 8
    __UNIT_PUMPECS = 9
    __UNIT_PUMPPOWER = 10
    __UNIT_BURNER = 11
    __UNIT_FANSPEED = 12
    __UNIT_TEMPADAYTARGET = 13
    __UNIT_TEMPANIGHTTARGET = 14
    __UNIT_TEMPAANTIFREEZETARGET = 15
    __UNIT_TEMPBDAYTARGET = 16
    __UNIT_TEMPBNIGHTTARGET = 17
    __UNIT_TEMPBANTIFREEZETARGET = 18
    __UNIT_TEMPECSDAYTARGET = 19
    __UNIT_TEMPECSNIGHTTARGET = 20
    __UNIT_STATEA = 21
    __UNIT_STATEB = 22
    __UNIT_MODEA = 23
    __UNIT_MODEB = 24
    __UNIT_MODEECS = 25
    __UNIT_BURNERPOWER = 26
    __UNIT_BOILERTEMP = 27
    __UNIT_BOILERTEMPATARGET = 28
    __UNIT_RETURNTEMP = 29
    __UNIT_SMOKETEMP = 30
    __UNIT_WATERPRESS = 31
    __UNIT_ALARM = 32
    __UNIT_DATE = 33
    __UNIT_TIME = 34

    #device unit details
    __UNITS = [
        # Unit, Name, TypeName, Type, Subtype, Options, Used, ModBus address, bit, convert function
        [__UNIT_TYPE, "Boiler Type","Text", 0, 0, {}, 0,457,0,None],
        [__UNIT_CTRL, "Software Version", "Text", 0, 0, {}, 0,3,0,None],
        [__UNIT_TEMPINTA, "Temp Interne A","Temperature", 0, 0, {}, 1,18,0,diem3Float],
        [__UNIT_TEMPINTB, "Temp Interne B","Temperature", 0, 0, {}, 0,27,0,diem3Float],
        [__UNIT_TEMPEXT, "Temp Externe","Temperature", 0, 0, {}, 1,7,0,diem3Float],
        [__UNIT_TEMPECS, "Temp ECS","Temperature", 0, 0, {}, 1,62,0,diem3Float],
        [__UNIT_PUMPA, "Pump A", "Text", 243,31, {'Custom':'1'}, 0,__DIEM3_BASE_ECS,4,diem3Bit],
        [__UNIT_PUMPB, "Pump B", "Text", 243,31, {'Custom':'1'}, 0,__DIEM3_OPTIONS_BC,4,diem3Bit],
        [__UNIT_PUMPECS, "Hot Water Pump", "Text", 243,31, {'Custom':'1'}, 0,__DIEM3_BASE_ECS,5,diem3Bit],
        [__UNIT_PUMPPOWER, "Pump Power", "Text", 243,31, {'Custom':'1;%'}, 0,463,0,None],
        [__UNIT_BURNER, "Burner", "Text", 243,31, {'Custom':'1'}, 0,__DIEM3_BASE_ECS,3,diem3Bit],
        [__UNIT_FANSPEED, "Fan Speed", "Text", 243,31, {'Custom':'1;tr/mn'}, 0,__DIEM3_FAN_SPEED,0,None],
        [__UNIT_TEMPADAYTARGET, "Cons Temp Jour A","Temperature", 0, 0, {}, 0,14,0,diem3Float],
        [__UNIT_TEMPANIGHTTARGET, "Cons Temp Nuit A","Temperature", 0, 0, {}, 0,15,0,diem3Float],
        [__UNIT_TEMPAANTIFREEZETARGET, "Cons Temp Antigel A","Temperature", 0, 0, {}, 0,16,0,diem3Float],
        [__UNIT_TEMPBDAYTARGET, "Cons Temp Jour B","Temperature", 0, 0, {}, 0,23,0,diem3Float],
        [__UNIT_TEMPBNIGHTTARGET, "Cons Temp Nuit B","Temperature", 0, 0, {}, 0,24,0,diem3Float],
        [__UNIT_TEMPBANTIFREEZETARGET, "Cons Temp Antigel B","Temperature", 0, 0, {}, 0,25,0,diem3Float],
        [__UNIT_TEMPECSDAYTARGET, "Cons Jour ECS","Temperature", 0, 0, {}, 0,59,0,diem3Float],
        [__UNIT_TEMPECSNIGHTTARGET, "Cons Nuit ECS","Temperature", 0, 0, {}, 0,96,0,diem3Float],
        [__UNIT_STATEA, "Etat Circuit A", "Text", 0, 0, {}, 0,0,0,None],
        [__UNIT_STATEB, "Etat Circuit B", "Text", 0, 0, {}, 0,0,0,None],
        [__UNIT_MODEA, "Mode Circuit A", "Text", 0, 0, {}, 0,17,0,diem3ModeLabel],
        [__UNIT_MODEB, "Mode Circuit B", "Text", 0, 0, {}, 0,26,0,diem3ModeLabel],
        [__UNIT_MODEECS, "Mode ECS", "Text", 0, 0, {}, 0,17,0,diem3EcsModeLabel],
        [__UNIT_BURNERPOWER, "Burner Power", "Text", 243,31, {'Custom':'1;%'}, 0,455,0,diem3BurnerPower],
        [__UNIT_BOILERTEMP, "Boiler Temperature","Temperature", 0, 0, {}, 0,75,0,diem3Float],
        [__UNIT_BOILERTEMPATARGET, "Boiler Temperature Target","Temperature", 0, 0, {}, 0,21,0,diem3Float],
        [__UNIT_RETURNTEMP, "Water Return Temperature","Temperature", 0, 0, {}, 0,453,0,diem3Float],
        [__UNIT_SMOKETEMP, "Smoke Temperature","Temperature", 0, 0, {}, 0,454,0,diem3Float],
        [__UNIT_WATERPRESS, "Water Pressure","",243,31, {'Custom':'1;Bar'}, 0,456,0,diem3Float],
        [__UNIT_ALARM, "Alarm", "Text", 0, 0, {}, 0,465,0,diem3AlarmLabel],
        [__UNIT_DATE, "Date", "Text", 0, 0, {}, 0,0,0,None],
        [__UNIT_TIME, "Time", "Text", 0, 0, {}, 0,0,0,None]
    ]
    
    #Diematic3 register bank definition
    __BANKS=[
    #start address, length
    [1,63],
    [64,64],
    [384,64],
    [448,23]
    ]
    
    #diematic3 register content
    diematic3Reg=dict()

              
    #next bank to be refreshed
    nextBank=0
    
    #Unit refresh period in second
    REFRESH_PERIOD=60
    
    tcpConn=None
    
    def __init__(self):
        #create modBus handler
        self.modBus=ModBusDD.Interface()
        return

    def onStart(self):
        Domoticz.Log("onStart called")
        
        if Parameters["Mode6"] != "Normal":
            Domoticz.Debugging(1)
        self.tcpConn = Domoticz.Connection(Name="Diematic3", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
        self.tcpConn.Connect()
        
        #timestamp of last data refresh
        self.refreshTime=time.time()-BasePlugin.REFRESH_PERIOD
        
        #Device creation
        if len(Devices) ==0:
            for unit in self.__UNITS:
                Domoticz.Device(Unit=unit[0],
                                Name=unit[1],
                                TypeName=unit[2],
                                Type=unit[3],
                                Subtype=unit[4],
                                Options=unit[5],
                                Used=unit[6]).Create()
        
        #Domoticz.Log("Plugin has " + str(len(Devices)) + " devices associated with it.")
        DumpConfigToLog()
        self.modBus.connect(self.tcpConn)

    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")
        #set heartbeat to 1s to distinghish master from slave mode of the DeDietrich modbus (switch every 5 s)
        Domoticz.Heartbeat(1)

    def onMessage(self, Connection, Data):
        byteCount=self.modBus.dataRx(Data,self.diematic3Reg)
        
        #if byte Count is not nul , relaunch a request for next bank
        if (byteCount!=0):
            self.nextBank+=1

            #if there's still a bank to be read and modBus is still in master mode
            if (self.nextBank < len(self.__BANKS)) and  self.modBus.masterMode:
                Domoticz.Log("Request next bank " + str(self.nextBank) +" @" + str(self.__BANKS[self.nextBank][0]) + " to be read")
                self.modBus.dataRequest(0x0A,self.__BANKS[self.nextBank][0],self.__BANKS[self.nextBank][1])

        #if all banks have been read           
        if (self.nextBank >= len(self.__BANKS)):
            self.nextBank=0
            self.refreshTime+=BasePlugin.REFRESH_PERIOD
            Domoticz.Log("All register banks have been read") 
                
            #devices (depending from one register) update
            for unit in self.__UNITS:
                if (unit[7] in self.diematic3Reg):
                    if (unit[9] is not None):
                        sValue=unit[9](self.diematic3Reg[unit[7]],unit[8])
                        if Devices[unit[0]].sValue!=sValue:
                            Devices[unit[0]].Update(nValue=0, sValue=sValue)
                        else:
                            Devices[unit[0]].Touch()
                            
                    else:
                        if Devices[unit[0]].sValue!=str(self.diematic3Reg[unit[7]]):
                            Devices[unit[0]].Update(nValue=0, sValue=str(self.diematic3Reg[unit[7]]))
                        else:
                            Devices[unit[0]].Touch()

            #devices (depending from several registers) update
            #time
            if set((4,5)) <= self.diematic3Reg.keys():
                nextValue="{:02}:{:02}".format(self.diematic3Reg[4],self.diematic3Reg[5])
                device=Devices[BasePlugin.__UNIT_TIME]
                if device.sValue!=nextValue:
                    Devices[BasePlugin.__UNIT_TIME].Update(nValue=0, sValue=nextValue)
            #date
            if set((6,108,109,110)) <= self.diematic3Reg.keys():
                nextValue="{} {:02}/{:02}/{:02}".format(BasePlugin.__DAY_LABELS[self.diematic3Reg[6]],self.diematic3Reg[108],self.diematic3Reg[109],self.diematic3Reg[110])
                device=Devices[BasePlugin.__UNIT_DATE]
                if device.sValue!=nextValue:
                    Devices[BasePlugin.__UNIT_DATE].Update(nValue=0, sValue=nextValue)
            
            #Boiler status A
            if set((BasePlugin.__DIEM3_BASE_ECS,BasePlugin.__DIEM3_FAN_SPEED)) <= self.diematic3Reg.keys():
                #if ECS pump is on  OR pump power=100, burner off, and fan on) (workaround bug on BASE_ECS bit 5 (pump ecs) which is ot always set to 1) 
                if (((self.diematic3Reg[BasePlugin.__DIEM3_BASE_ECS] & 0x20) !=0) or ((self.diematic3Reg[BasePlugin.__DIEM3_FAN_SPEED] > BasePlugin.__FAN_SPEED_MIN ) and ((self.diematic3Reg[BasePlugin.__DIEM3_BASE_ECS] & 0x08)== 0))):
                    #mode is water heater
                    boiler_mode_A= BasePlugin.__STATUS_LABELS[2]
                #else if PUMP_A is ON, boiler mode is heater
                elif ((self.diematic3Reg[BasePlugin.__DIEM3_BASE_ECS] & 0x10) !=0):
                    boiler_mode_A= BasePlugin.__STATUS_LABELS[1]
                else:
                    boiler_mode_A= BasePlugin.__STATUS_LABELS[0]
                    
                device=Devices[BasePlugin.__UNIT_STATEA]
                if device.sValue!=boiler_mode_A:
                    Devices[BasePlugin.__UNIT_STATEA].Update(nValue=0, sValue=boiler_mode_A)
                    
            #Boiler status B
            if set((BasePlugin.__DIEM3_BASE_ECS,BasePlugin.__DIEM3_OPTIONS_BC)) <= self.diematic3Reg.keys():
                #if ECS pump is on  OR pump power=100, burner off, and fan on) (workaround bug on BASE_ECS bit 5 (pump ecs) which is ot always set to 1) 
                if (self.diematic3Reg[BasePlugin.__DIEM3_BASE_ECS] & 0x20) !=0 :
                    #mode is water heater
                    boiler_mode_B= BasePlugin.__STATUS_LABELS[2]
                #else if PUMP_B is ON, boiler mode is heater
                elif ((self.diematic3Reg[BasePlugin.__DIEM3_OPTIONS_BC] & 0x10) !=0):
                    boiler_mode_B= BasePlugin.__STATUS_LABELS[1]
                else:
                    boiler_mode_B= BasePlugin.__STATUS_LABELS[0]
                    
                device=Devices[BasePlugin.__UNIT_STATEB]
                if device.sValue!=boiler_mode_B:
                    Devices[BasePlugin.__UNIT_STATEB].Update(nValue=0, sValue=boiler_mode_B)
        
            #reset registers
            self.diematic3Reg=dict()

        Domoticz.Log("onMessage called  :"+ str(len(Data)) +" bytes read")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")
        Domoticz.Heartbeat(10)
        self.tcpConn.Connect()

    def onHeartbeat(self):
        self.modBus.oneSecTimer()
        #if master mode is available (boiler in slave mode)
        if self.modBus.masterReady and ((time.time() > self.refreshTime+BasePlugin.REFRESH_PERIOD) or (self.nextBank !=0) ):
            #reinit diematic3 register
            self.diematic3Reg=dict()
            #launch diematic3 register polling
            self.modBus.dataRequest(0x0A,self.__BANKS[self.nextBank][0],self.__BANKS[self.nextBank][1])

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
