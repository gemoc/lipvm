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