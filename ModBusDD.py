import Domoticz

class Interface:
    # standard
    READ_COILS = 0x01
    READ_DISCRETE_INPUTS = 0x02
    READ_HOLDING_REGISTERS = 0x03
    READ_INPUT_REGISTERS = 0x04
    WRITE_SINGLE_COIL = 0x05
    WRITE_SINGLE_REGISTER = 0x06
    WRITE_MULTIPLE_COILS = 0x0F
    WRITE_MULTIPLE_REGISTERS = 0x10

    ######################
    # init
    ######################
    def __init__(self,slaveAddress=0):
        
        #internal timer
        self.timer=0

        #init status
        self.resetStatus()
        
    def cancelAckWaiting(self):
        #reset waited answer frame information
        self.ackFrameSlaveAddress=0
        self.ackFrameFunctionCode=0
        self.ackFrameDataAddress=0
        self.ackFrameDataLength=0
                
    def resetStatus(self):
        #init timer for master slave detection
        self.masterSlaveTimer=-2
        self.masterReady=False
        self.masterMode=False
        self.cancelAckWaiting()
    
    ######################
    # connection
    ######################
    def connect(self,connection):
        self.connect=connection
    
    ######################
    # one second heart beat
    ######################
    def oneSecTimer(self):
        self.masterSlaveTimer+=1
        #set the flag indicating beginning of Master Mode
        if (self.masterSlaveTimer==0):
            #cancel waited answer frame information
            self.cancelAckWaiting()
            self.masterReady=True
        else:
            self.masterReady=False
        
        #set the flag indicating the mode
        if (self.masterSlaveTimer >=0) and (self.masterSlaveTimer <3):
            self.masterMode=True
            Domoticz.Log("MASTER MODE :" + str(self.masterSlaveTimer))
        else :
            self.masterMode=False
            Domoticz.Log("SLAVE MODE :" + str(self.masterSlaveTimer))
    
    ######################
    # receive data as Slave
    ######################
    def dataRx(self,data,regs):
        serialBuffer=bytes()
        serialBuffer+=data
        i=0

        #if interface is in master mode and waiting for an ack
        if self.masterMode and (self.ackFrameSlaveAddress!=0):
            if (len(serialBuffer) >= 3) and (serialBuffer[0]==self.ackFrameSlaveAddress) and (serialBuffer[1]==self.ackFrameFunctionCode):
                #if interface is waiting for a READ_HOLDING_REGISTERS command and frame length is correct
                if (serialBuffer[1]==self.READ_HOLDING_REGISTERS) and (serialBuffer[2]==self.ackFrameDataLength) and (len(serialBuffer) >= 5 +self.ackFrameDataLength):
                    #if checksum is correct
                    high_crc,low_crc = divmod(self.crc16(serialBuffer[:self.ackFrameDataLength+3]), 0x100)
                    if (low_crc==serialBuffer[self.ackFrameDataLength+3]) and (high_crc==serialBuffer[self.ackFrameDataLength+4]):
                        Domoticz.Log("Ack Received")
                        #data extraction
                        for i in range(int(self.ackFrameDataLength / 2)):
                            regs[i+self.ackFrameDataAddress]=0x100*serialBuffer[3+2*i ]+ serialBuffer[4+2*i]
                        Domoticz.Log("Data :"+str(regs))
                        
                        #no more ack are waited for
                        self.cancelAckWaiting()
                        
                    else:
                        #checksum error
                        Domoticz.Log("Checksum error :"+hex(low_crc)+":"+hex(high_crc)+" vs "+hex(serialBuffer[self.ackFrameDataLength+3])+":"+hex(serialBuffer[self.ackFrameDataLength+4]))
                        self.resetStatus()
                else:
                    #reinit status
                    Domoticz.Log("READ_HOLDING_REGISTERS Ack error:")
                    self.resetStatus()
            else:
                #reinit status
                Domoticz.Log("Ack error")
                self.resetStatus()
        else :
            #reinit status
            self.resetStatus()

        Domoticz.Log("onMessage called ("+str(self.timer)+") :"+ str(len(serialBuffer)) +" bytes read")
        return i

    #######################################
    # request data from Slave (master mode)
    #######################################
    def dataRequest(self,slaveAddress, address, nb):
        frame=bytearray()
        
        #if link ready and modBus interface Ready for master mode and ackFrame not already beeing waited for
        if (self.connect is not None) and self.masterMode and (self.ackFrameSlaveAddress==0):
            if (slaveAddress <1 or slaveAddress >247):
                return False
            if (nb <1 or nb >64):
                return False
            #modBus frame building
            frame.append(slaveAddress)
            frame.append(self.READ_HOLDING_REGISTERS)
            #address high , low
            high,low = divmod(address, 0x100)
            frame.append(high)
            frame.append(low)
            #number of bytes requested
            frame.append(0)
            frame.append(nb)
            #crc, low byte first
            high,low = divmod(self.crc16(frame), 0x100)
            frame.append(low)
            frame.append(high)
            #final 0, specific to De Dietrich
            frame.append(0)

            self.connect.Send(frame)
            self.ackFrameSlaveAddress=slaveAddress
            self.ackFrameFunctionCode=self.READ_HOLDING_REGISTERS
            self.ackFrameDataAddress=address
            self.ackFrameDataLength=nb*2
        else:
            return False
        return True

    ######################
    # compute CRC of frame
    ######################
    def crc16(self,frame):
        """Compute CRC16
        :param frame: frame
        :type frame: class bytes (Python3)
        :returns: CRC16
        :rtype: int
        """
        crc = 0xFFFF
        for index, item in enumerate(bytearray(frame)):
            next_byte = item
            crc ^= next_byte
            for i in range(8):
                lsb = crc & 1
                crc >>= 1
                if lsb:
                    crc ^= 0xA001
        return crc
