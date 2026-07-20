from abc import ABC, abstractmethod

class ActionSimulationModel(ABC):

    @abstractmethod
    def evaluate(self):
        raise NotImplementedError("Sub-class must implement this method.")


class Print(ActionSimulationModel):

    def __init__(self, msg):
        self.msg = msg

    def evaluate(self):
        print(self.msg)

