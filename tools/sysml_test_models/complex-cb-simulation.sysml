package Common {
    part def Machine;
    private import ScalarValues::*;

    package Messages {
        item def EventMessage;
    } // package Messages

    attribute def FactoryCoordinate {
        attribute x : Real;
        attribute y : Real;
        attribute degrees: Real;
    }
} // package Common


package ConveyorBeltSystem {
    private import ScalarValues::*;
    private import Common::*;
    private import Common::Messages::*;

    package ConveyorBeltCommands {
        enum def ConveyorCommandKind {
            MOVE_TO_SENSOR;
            MOVE_OUT;
            MOVE_NB_STEPS;
            STOP;
            STATUS_REQUEST;
        }

        enum def DirectionKind {
            FORWARD;
            BACKWARD;
        }

        action def MoveToSensor {
            in direction : DirectionKind;
        }

        action def MoveOut {
            in direction : DirectionKind;
        }

        action def MoveNbSteps {
            in steps : Integer;
            in direction : DirectionKind;
        }

        action def Stop {}

        action def StatusRequest {}
    } // package ConveyorBeltCommands

    package ConveyorBeltMessages {
        item def FeedFreeEventMessage :> EventMessage;
        item def SwapBusyEventMessage :> EventMessage;
        item def CBCommandSuccessEventMessage :> EventMessage;
        item def StopEventMessage :> EventMessage;
        item def StartEventMessage :> EventMessage;
    } // package ConveyorBeltMessages

    package ConveyorBelt {
        private import ConveyorBeltSystem::ConveyorBeltCommands::*;
        part def ConveyorBeltMachine specializes Machine {
            perform action moveToSensor : MoveToSensor;
            perform action moveOut : MoveOut;
            perform action moveNbSteps : MoveNbSteps;
            perform action stop : Stop;
            perform action statusRequest : StatusRequest;

            attribute currentCommand : ConveyorCommandKind;
            attribute direction : DirectionKind;

            attribute currentStepCount : Integer;
            attribute targetStepCount : Integer;

            attribute conveyorSensFeed : Boolean;
            attribute conveyorSensSwap : Boolean;
            attribute conveyorSensImpulse : Integer;
            attribute placementCoordinate : FactoryCoordinate;
        }
    } // package ConveyorBelt
} // package ConveyorBeltSystem

package ConveyorBeltStates {
    private import Common::*;
    private import ConveyorBeltSystem::*;
    private import ConveyorBeltSystem::ConveyorBeltCommands::*;
    private import ConveyorBeltSystem::ConveyorBeltMessages::*;

    state def ConveyorBeltComplexMissionOne {
        in conveyorBelt : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine;
        entry;
        then Idle;

        state Idle;
        accept when conveyorBelt.conveyorSensFeed == true
            do conveyorBelt.moveToSensor {
                in direction = DirectionKind::FORWARD;
            }
            then Continue;

        state Continue {
            entry conveyorBelt.moveToSensor {
                in direction = DirectionKind::FORWARD;
            }
        }
        accept when conveyorBelt.conveyorSensSwap == true
            then WaitForPickup;
        accept StopEventMessage
            then Idle;

        state WaitForPickup;
        accept when conveyorBelt.conveyorSensSwap == false
            then Continue;

    }

    state def ConveyorBeltComplexMissionTwo {
        in conveyorBelt : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine;
        entry;
        then Start;

        state Start {
            entry conveyorBelt.moveToSensor {
                in direction = DirectionKind::FORWARD;
            }
        }
        accept when conveyorBelt.conveyorSensSwap == true
            then WaitForPickup;
        accept StopEventMessage
            then Idle;

        state WaitForPickup;
        accept when conveyorBelt.conveyorSensSwap == false
            then Start;
        accept StopEventMessage
            then Idle;
        
        state Idle;
        accept StartEventMessage
            then Start;

    }
} // package ConveyorBeltStates

package Main {

    private import ConveyorBeltSystem::ConveyorBelt::*;
    private import ConveyorBeltStates::*;

    part cb1 : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 10.0;
            attribute :>> y = 10.0;
            attribute :>> degrees = 0.0;
        }
    }

    part cb2 : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 25.0;
            attribute :>> y = 25.0;
            attribute :>> degrees = 90.0;
        }
    }

    state cbSimulationSimple: ConveyorBeltComplexMissionOne {
        in conveyorBelt = cb1;
    }

    state cbSimulationSpecial: ConveyorBeltComplexMissionTwo {
        in conveyorBelt = cb2;
    }

}

