from languages.sysmlv2.simulation_models.fischertechnik.custom_attribute import FactoryCoordinate
from languages.sysmlv2.simulation_models.fischertechnik.enums import DirectionKind, ConveyorCommandKind

class ConveyorBeltMachine:

    def __init__(self):

        self._currentCommand: ConveyorCommandKind
        self._direction: DirectionKind
        self._currentStepCount : int = 0
        self._targetStepCount : int = 0

        self._conveyorSensFeed : bool = False
        self._conveyorSensSwap : bool = False
        self._conveyorSensImpulse : int = 0
        self._placementCoordinate : FactoryCoordinate

    @property
    def placementCoordinate(self):
        return self._placementCoordinate

    @placementCoordinate.setter
    def placementCoordinate(self, value):
        self._placementCoordinate = value

    @property
    def conveyorSensFeed(self):
        return self._conveyorSensFeed

    @property
    def conveyorSensSwap(self):
        return self._conveyorSensSwap

    @property
    def conveyorSensImpulse(self):
        return self._conveyorSensImpulse

    def moveToSensor(self, direction):
        pass

    def moveOut(self, direction):
        pass

    def MoveNbSteps(self, steps, direction):
        pass

    def stop(self):
        pass

    def statusRequest(self):
        pass
