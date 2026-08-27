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

package VacuumGripperSystem {
    private import ScalarValues::*;
    private import Common::*;
    private import Common::Messages::*;

    package VacuumGripperCommands {
        enum def VacuumGripperCommandKind {
            GO_TO_POSITION;
            MOVE;
            PICK;
            PLACE;
            SETUP;
            STATUS_REQUEST;
            GRIP;
            RELEASE;
            STOP;
            MOVE_TO_SAFE_POSITION;
            RETRACT_ARM;
        }

        enum def ExecutionStatusKind {
            MUST_CONTINUE;
            DONE;
        }

        attribute def Position3D {
            attribute vertical : Real;
            attribute horizontal : Real;
            attribute rot : Real;
        }

        action def GoToPosition {
            in targetPosition : Position3D;
        }

        action def Move {
            in startPosition : Position3D;
            in endPosition : Position3D;
        }

        action def Pick {
            in targetPosition : Position3D;
            doc
            /* Moves to the pickup area, activates gripping, and lifts the payload. */
        }

        action def Place {
            in targetPosition : Position3D;
            doc
            /* Moves to the drop-off area, releases the payload, and retreats. */
        }

        action def Setup {}

        action def Grip {
            out attribute vacuumActValve : Boolean = true;
            out attribute vacuumActCompressorOn : Boolean = true;
        }

        action def Release {
            out attribute vacuumActValve : Boolean = false;
            out attribute vacuumActCompressorOn : Boolean = false;
        }

        action def Stop {}

        action def MoveToSafePosition {}

        action def RetractArm {}

        action def StatusRequest {}
    } // package VacuumGripperCommands

    package VacuumGripperMessages {
        item def VGRCommandSuccessEventMessage :> EventMessage;
    } // package VacuumGripperMessages

    package VacuumGripper {
        private import VacuumGripperSystem::VacuumGripperCommands::*;

        part def VacuumGripperMachine specializes Machine {
            perform action goToPosition : GoToPosition {
                in targetPosition : Position3D;
            }
            perform action move : Move {
                in startPosition : Position3D;
                in endPosition : Position3D;
            }
            perform action pick : Pick {
                in targetPosition : Position3D;
            }
            perform action place : Place {
                in targetPosition : Position3D;
            }
            perform action setup : Setup;
            perform action statusRequest : StatusRequest;
            perform action grip : Grip;
            perform action release : Release;
            perform action stop : Stop;
            perform action moveToSafePosition : MoveToSafePosition;
            perform action retractArm : RetractArm;

            attribute currentCommand : VacuumGripperCommandKind;
            attribute executionStatus : ExecutionStatusKind;

            attribute verticalEncoder : Real;
            attribute armEncoder : Real;
            attribute rotEncoder : Real;

            attribute expectedVerticalEncoderValue : Real;
            attribute expectedArmEncoderValue : Real;
            attribute expectedRotationEncoderValue : Real;

            attribute vacuumActCompressorOn : Boolean;
            attribute vacuumActValve : Boolean;

            attribute placementCoordinate : FactoryCoordinate;
        }
    } // package VacuumGripper
} // package VacuumGripperSystem

package VGRStates {
    private import Common::*;
    private import VacuumGripperSystem::*;
    private import VacuumGripperSystem::VacuumGripperCommands::*;
    private import VacuumGripperSystem::VacuumGripperMessages::*;
    private import VacuumGripperSystem::VacuumGripper::*;
    private import ConveyorBeltSystem::ConveyorBeltMessages::*;

    state def VGRMissionWith2CB {
        
        /* Parts involved in this mission*/
        in vgrOne : VacuumGripperSystem::VacuumGripper::VacuumGripperMachine;
        in feederCB: ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine;
        in transportCB: ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine;

        /* parameters for some VGR actions*/        
        in pickFromFeederPosition: Position3D;
        in placeToTransportPosition: Position3D;

        entry vgrOne.setup;
        then SafePosition;

        /* First initialization */
        state SafePosition;
        accept VGRCommandSuccessEventMessage via vgrOne 
            do vgrOne.moveToSafePosition
            then Idle;

        state Idle; 
        accept SwapBusyEventMessage via feederCB
            do vgrOne.pick {
                in targetPosition = pickFromFeederPosition;
            }
            then WaitForPickup;
        accept StopEventMessage via vgrOne
            do vgrOne.moveToSafePosition
            then FullStop;

        state WaitForPickup;
        accept VGRCommandSuccessEventMessage via vgrOne
            do vgrOne.place {
                in targetPosition = placeToTransportPosition;
            }
            then WaitForPlace;
        
        state WaitForPlace;
        accept VGRCommandSuccessEventMessage via vgrOne
            then SafePosition;

        state FullStop {
            entry vgrOne.stop;
        }
        accept StartEventMessage via vgrOne
            then Idle;
    }
} // package VGRStates


package ConveyorBeltStates {
    private import Common::*;
    private import ConveyorBeltSystem::*;
    private import ConveyorBeltSystem::ConveyorBeltCommands::*;
    private import ConveyorBeltSystem::ConveyorBeltMessages::*;

    state def ConveyorBeltSimpleMission {
        in conveyorBelt : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine;
        entry;
        then Start;

        state Start {
            entry conveyorBelt.moveToSensor {
                in direction = DirectionKind::FORWARD;
            }
        }
        accept SwapBusyEventMessage via conveyorBelt
            then WaitForPickup;
        accept StopEventMessage
            then Idle;

        state WaitForPickup;
        accept when conveyorBelt.conveyorSensSwap == false
            then Start;
        accept StopEventMessage via conveyorBelt
            then Idle;
        
        state Idle;
        accept StartEventMessage via conveyorBelt
            then Start;

    }
} // package ConveyorBeltStates

package Main {

    private import Common::*;
    private import ConveyorBeltSystem::ConveyorBelt::*;
    private import ConveyorBeltStates::*;
    private import VacuumGripperSystem::VacuumGripper::*;
    private import VacuumGripperSystem::VacuumGripperCommands::*;
    private import VGRStates::*;

    part cb1 : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 13.0;
            attribute :>> y = 20.0;
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

    part vgr1: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 20.0;
            attribute :>> y = 27.0;
            attribute :>> degrees = 0.0;
        }
    }

    state cbFeederMission: ConveyorBeltSimpleMission {
        in conveyorBelt = cb1;
    }

    state cbTransportMission: ConveyorBeltSimpleMission {
        in conveyorBelt = cb2;
    }

    state vgrMission: VGRMissionWith2CB {
        /* Parts involved in this mission*/
        in vgrOne = vgr1;
        in feederCB = cb1;
        in transportCB = cb2;

        /* parameters for some VGR actions*/        
        in pickFromFeederPosition {
            attribute :>> vertical = 940.0;
            attribute :>> horizontal = 0.0;
            attribute :>> rot = 0.0;
        }
        in placeToTransportPosition {
            attribute :>> vertical =940.0;
            attribute :>> horizontal = 0.0;
            attribute :>> rot = 1750.0;
        }
    }

}

