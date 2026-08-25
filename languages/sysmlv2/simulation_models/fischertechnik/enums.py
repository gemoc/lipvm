from enum import Enum


class DirectionKind(Enum):
    BACKWARD = 0
    FORWARD = 1

class ConveyorCommandKind(Enum):

    MOVE_TO_SENSOR = 'MTS'
    MOVE_OUT = 'MO'
    MOVE_NB_STEPS = 'MNS'
    STOP = 'S'
    STATUS_REQUEST = 'RS'

class ExecutionStatusKind(Enum):
    MUST_CONTINUE = 'MC'
    DONE = 'DN'

class VacuumGripperCommandKind(Enum):
    GO_TO_POSITION = 'GTP'
    MOVE = 'MV'
    PICK = 'PCK'
    PLACE = 'PLC'
    SETUP = 'STP'
    STATUS_REQUEST = 'SR'
    GRIP = 'GR'
    RELEASE = 'R'
    STOP = 'S'
    MOVE_TO_SAFE_POSITION = 'MTSP'
    RETRACT_ARM = 'RA'

    #The commands below are not exist in reality, just for demo purposes
    EXTEND_ARM = 'EA'


class TokenColorKind(Enum):
    BLUE = 0
    WHITE = 1
    RED = 2