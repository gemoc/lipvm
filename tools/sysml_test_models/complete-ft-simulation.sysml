package Common {
    part def Machine;
    private import ScalarValues::*;

    package Messages {
        item def EventMessage;
        item def BufferedMessage;
    } // package Messages

    attribute def FactoryCoordinate {
        attribute x : Real;
        attribute y : Real;
        attribute degrees: Real;
    }

    enum def TokenColorKind {
        RED;
        BLUE;
        WHITE;
    }

} // package Common

package TokenProducerSystem {

    private import ScalarValues::*;
    private import Common::*;
    private import Common::Messages::*;

    package TokenProducerCommands {

        enum def TokenProducerCommandKind {
            STOP;
            EMIT_TOKEN;
            EMPTY_PLATFORM;
            RANDOM_EMIT_TOKEN;
        }

        action def EmitToken {
            in desiredColor: TokenColorKind;
        }

        action def RandomEmitToken {

        }

        action def Stop {

        }

        action def EmptyPlatform {

        }

    } // package TokenProducerCommands

    package TokenProducerMessages {
        item def TokenProducerSuccessEventMessage :> EventMessage;
        item def TokenPlatformBusyEventMessage :> EventMessage;
        item def TokenPlatformFreeEventMessage :> EventMessage;
    } // package TokenProducerMessages

    package TokenProducer {
        private import TokenProducerSystem::TokenProducerCommands::*;
        
        part def TokenProducerMachine specializes Machine {
            perform action emitToken : EmitToken;
            perform action stop : Stop;
            perform action emptyPlatform : EmptyPlatform;
            perform action randomEmitToken : RandomEmitToken;

            attribute platformSens : Boolean;
            attribute currentCommand : TokenProducerCommandKind;
            attribute lastUsedTokenColor: TokenColorKind;

            attribute placementCoordinate : FactoryCoordinate;
        }
    } // package TokenProducer

    package TokenProducerStates {
        
        private import Common::*;
        private import TokenProducerSystem::*;
        private import TokenProducerSystem::TokenProducerCommands::*;
        private import TokenProducerSystem::TokenProducerMessages::*;
        private import TokenProducerSystem::TokenProducer::*;

        state def TokenProducerSimpleMission {
            
            in tokenProducerMachine: TokenProducerMachine;

            entry;
            then ProducingTokenRandomly;

            state ProducingTokenRandomly {
                entry tokenProducerMachine.randomEmitToken;
            }
            accept TokenProducerSuccessEventMessage via tokenProducerMachine
                then WaitPlatformFree;
            
            state WaitPlatformFree;
            accept TokenPlatformFreeEventMessage via tokenProducerMachine
                then ProducingTokenRandomly;
        }

    } // package TokenProducer

} // package TokenProducerSystem

package TokenDepoSystem {

    private import ScalarValues::*;
    private import Common::*;
    private import Common::Messages::*;

    package TokenDepoCommands {

        enum def TokenDepoCommandKinds {
            STORE_TOKEN;
            EMPTY_RECEIVER;
            STOP;
        }

        action def StoreToken { }
        action def Stop {}
        action def EmptyReceiver {}

    } // package TokenDepoCommands

    package TokenDepoMessages {
        item def TokenDepoSuccessEventMessage :> EventMessage;
        item def ReceiverEmptyEventMessage :> EventMessage;
        item def ReceiverBusyEventMessage :> EventMessage;
    } // package TokenDepoMessages

    package TokenDepo {

        private import TokenDepoSystem::TokenDepoCommands::*;

        part def TokenDepoMachine specializes Machine {
            
            perform action storeToken : StoreToken;
            perform action stop : Stop;
            perform action emptyReceiver : EmptyReceiver;

            attribute tokenCount : Integer;
            attribute receiverSens : Boolean;
            attribute currentCommand : TokenDepoCommandKinds;

            attribute placementCoordinate : FactoryCoordinate;
        }

    } // package TokenDepo

    package TokenDepoStates {
        
        private import TokenDepoSystem::TokenDepo::*;
        private import TokenDepoSystem::TokenDepoMessages::*;
        private import TokenDepoSystem::TokenDepoCommands::*;

        state def TokenDepoSimpleMission {

            in tokenDepoInstance : TokenDepoMachine;

            entry;
            then Idle;

            state Idle;
            accept when tokenDepoInstance.receiverSens == true
                do tokenDepoInstance.storeToken
                then CheckCapacity;

            state CheckCapacity;
            accept when tokenDepoInstance.tokenCount > 30
                do tokenDepoInstance.emptyReceiver
                then StopMachine;
            accept when tokenDepoInstance.tokenCount <= 30
                then Idle;

            state StopMachine {
                entry tokenDepoInstance.storeToken;
            }
        }

    } // package TokenDepoStates
} // package TokenDepoSystem

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
            accept when conveyorBelt.conveyorSensSwap == true
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

    package VGRStates {
        private import Common::*;
        private import VacuumGripperSystem::*;
        private import VacuumGripperSystem::VacuumGripperCommands::*;
        private import VacuumGripperSystem::VacuumGripperMessages::*;
        private import VacuumGripperSystem::VacuumGripper::*;
        private import ConveyorBeltSystem::ConveyorBeltMessages::*;
        private import TokenProducerSystem::TokenProducerMessages::*;

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
                then Idle;

            state FullStop {
                entry vgrOne.stop;
            }
            accept StartEventMessage via vgrOne
                then Idle;
        }

        state def VGRPickTokenFromProducerAndPlace {
            
            /* Parts involved in this mission*/
            in vgr: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine;
            in tokenProducer: TokenProducerSystem::TokenProducer::TokenProducerMachine;

            /* parameters for some VGR actions*/        
            in pickFromProducerPosition: Position3D;
            in placePosition: Position3D; 

            entry vgr.setup;
            then SafePosition;

            /* First initialization */
            state SafePosition;
            accept VGRCommandSuccessEventMessage via vgr 
                do vgr.moveToSafePosition
                then Idle;
            
            state Idle; 
            accept when tokenProducer.platformSens == true
                do vgr.pick {
                    in targetPosition = pickFromProducerPosition;
                }
                then WaitForPickup;
            accept StopEventMessage via vgr
                do vgr.moveToSafePosition
                then FullStop;

            state WaitForPickup;
            accept VGRCommandSuccessEventMessage via vgr
                do vgr.place {
                    in targetPosition = placePosition;
                }
                then WaitForPlace;
            
            state WaitForPlace;
            accept VGRCommandSuccessEventMessage via vgr
                then Idle;
            
            state FullStop {
                entry vgr.stop;
            }
            accept StartEventMessage via vgr
                then Idle;

        }

        state def VGRPickTokenFromCBAndPlace {
            
            /* Parts involved in this mission*/
            in vgr: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine;
            in cb: ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine;

            /* parameters for some VGR actions*/        
            in pickFromCBPosition: Position3D;
            in placePosition: Position3D; 

            entry vgr.setup;
            then SafePosition;

            /* First initialization */
            state SafePosition;
            accept VGRCommandSuccessEventMessage via vgr 
                do vgr.moveToSafePosition
                then Idle;
            
            state Idle; 
            accept when cb.conveyorSensSwap == true
                do vgr.pick {
                    in targetPosition = pickFromCBPosition;
                }
                then WaitForPickup;
            accept StopEventMessage via vgr
                do vgr.moveToSafePosition
                then FullStop;

            state WaitForPickup;
            accept VGRCommandSuccessEventMessage via vgr
                do vgr.place {
                    in targetPosition = placePosition;
                }
                then WaitForPlace;
            
            state WaitForPlace;
            accept VGRCommandSuccessEventMessage via vgr
                then Idle;
            
            state FullStop {
                entry vgr.stop;
            }
            accept StartEventMessage via vgr
                then Idle;

        }

    } // package VGRStates
} // package VacuumGripperSystem

package SortingLineSystem {
    private import ScalarValues::*;
    private import Common::*;

    package SortingLineCommands {
        enum def SortingLineCommandKind {
            SORT;
            STOP;
        }

        enum def ExecutionStatusKind {
            MUST_CONTINUE;
            DONE;
        }

        action def Stop {}

        action def Eject {
            in color : TokenColorKind;
        }
    }

    package SortingLineMessages {
        private import Messages::*;
        private import SortingLineSystem::SortingLineCommands::*;

        item def BlueTokenAvailableBufferedMessage :> BufferedMessage;
        item def WhiteTokenAvailableBufferedMessage :> BufferedMessage;
        item def RedTokenAvailableBufferedMessage :> BufferedMessage;

        item def CommandSuccessEventMessage :> EventMessage;
    }

    package SortingLine {
        private import SortingLineSystem::SortingLineCommands::*;

        part def SortingLineMachine specializes Machine {
            perform action eject : Eject;
            perform action stop : Stop;

            attribute sensor_SL_in : Boolean = false;
            attribute sensor_SL_blue : Boolean = false;
            attribute sensor_SL_white : Boolean = false;
            attribute sensor_SL_red : Boolean = false;

            attribute placementCoordinate : FactoryCoordinate;
        }
    }

    package SortingLineMissions {
        private import Common::Messages::*;
        private import SortingLineSystem::*;
        private import SortingLineSystem::SortingLineCommands::*;
        private import SortingLineSystem::SortingLineMessages::*;
        private import VacuumGripperSystem::VacuumGripperCommands::*;
        private import VacuumGripperSystem::VacuumGripperMessages::*;

        doc
        /* Nominal mission scenario for SortingLine */
        state def SortingLineSimpleMission {
            in sortingLine : SortingLineSystem::SortingLine::SortingLineMachine;
            in vacuumGripper : VacuumGripperSystem::VacuumGripper::VacuumGripperMachine;

            in whiteTokenPickup : Position3D;
            in whiteTokenPlacement : Position3D;

            in blueTokenPickup : Position3D;    
            in blueTokenPlacement : Position3D;

            in redTokenPickup : Position3D;
            in redTokenPlacement : Position3D;

            entry;
            then Idle;

            state Idle;
            accept when sortingLine.sensor_SL_in == true then SortCMD;

            state SortCMD;
            accept CommandSuccessEventMessage then SendColorUpdate;

            state SendColorUpdate;
            accept when sortingLine.sensor_SL_blue == true
                do vacuumGripper.pick {
                    in targetPosition = blueTokenPickup;
                }
                then WaitToPlaceForBlue;
            accept when sortingLine.sensor_SL_white == true
                do vacuumGripper.pick {
                    in targetPosition = whiteTokenPickup;
                }
                then WaitToPlaceForWhite;
            accept when sortingLine.sensor_SL_red == true
                do vacuumGripper.pick {
                    in targetPosition = redTokenPickup;
                }
                then WaitToPlaceForRed;
            
            state WaitToPlaceForBlue;
            accept VGRCommandSuccessEventMessage via vacuumGripper
                do vacuumGripper.place {
                    in targetPosition = blueTokenPlacement;
                }
                then Idle;
            
            state WaitToPlaceForWhite;
            accept VGRCommandSuccessEventMessage via vacuumGripper
                do vacuumGripper.place {
                    in targetPosition = whiteTokenPlacement;
                }
                then Idle;
            
            state WaitToPlaceForRed;
            accept VGRCommandSuccessEventMessage via vacuumGripper
                do vacuumGripper.place {
                    in targetPosition = redTokenPlacement;
                }
                then Idle;
        }
    }

}

package Main {

    private import Common::*;
    private import ConveyorBeltSystem::ConveyorBelt::*;
    private import ConveyorBeltSystem::ConveyorBeltStates::*;
    private import ConveyorBeltSystem::ConveyorBeltStates::*;
    
    private import VacuumGripperSystem::VacuumGripper::*;
    private import VacuumGripperSystem::VacuumGripperCommands::*;
    private import VacuumGripperSystem::VGRStates::*;

    private import TokenProducerSystem::TokenProducer::*;
    private import TokenProducerSystem::TokenProducerMessages::*;

    private import TokenDepoSystem::TokenDepo::*;
    private import TokenDepoSystem::TokenDepoCommands::*;
    private import TokenDepoSystem::TokenDepoStates::*;

    private import SortingLineSystem::SortingLine::*;
    private import SortingLineSystem::SortingLineMissions::*;

    part tokenProd: TokenProducerSystem::TokenProducer::TokenProducerMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 5.0;
            attribute :>> y = 10.0;
            attribute :>> degrees = 0.0;
        }
    }

    part cbFeeder : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 13.0;
            attribute :>> y = 10.0;
            attribute :>> degrees = 0.0;
        }
    }

    part cbTransport : ConveyorBeltSystem::ConveyorBelt::ConveyorBeltMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 20.0;
            attribute :>> y = 17.0;
            attribute :>> degrees = 90.0;
        }
    }

    part tokenRedDepo : TokenDepoSystem::TokenDepo::TokenDepoMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 28.0;
            attribute :>> y = 32.0;
            attribute :>> degrees = 270.0;
        }
    }

    part tokenWhiteDepo : TokenDepoSystem::TokenDepo::TokenDepoMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 31.5;
            attribute :>> y = 32.0;
            attribute :>> degrees = 270.0;
        }
    }

    part tokenBlueDepo : TokenDepoSystem::TokenDepo::TokenDepoMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 35.0;
            attribute :>> y = 32.0;
            attribute :>> degrees = 270.0;
        }
    }

    part vgrTransToFeeder: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 20.0;
            attribute :>> y = 10.0;
            attribute :>> degrees = 0.0;
        }
    }

    part vgrPickProducer: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 10.0;
            attribute :>> y = 6.0;
            attribute :>> degrees = 90.0;
        }
    }

    part vgrPlaceSorting: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 24.0;
            attribute :>> y = 21.0;
            attribute :>> degrees = 0.0;
        }
    }

    part vgrPlaceDepo: VacuumGripperSystem::VacuumGripper::VacuumGripperMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 31.0;
            attribute :>> y = 27.0;
            attribute :>> degrees = 0.0;
        }
    }

    part slMachine: SortingLineSystem::SortingLine::SortingLineMachine {
        attribute :>> placementCoordinate {
            attribute :>> x = 32.0;
            attribute :>> y = 21.0;
            attribute :>> degrees = 0.0;
        }
    }

    state cbFeederMission: ConveyorBeltSimpleMission {
        in conveyorBelt = cbFeeder;
    }

    state cbTransportMission: ConveyorBeltSimpleMission {
        in conveyorBelt = cbTransport;
    }

    state tokenRedDepoMission: TokenDepoSimpleMission {
        in tokenDepoInstance = tokenRedDepo;
    }
    
    state tokenWhiteDepoMission: TokenDepoSimpleMission {
        in tokenDepoInstance = tokenWhiteDepo;
    }

    state tokenBlueDepoMission: TokenDepoSimpleMission {
        in tokenDepoInstance = tokenBlueDepo;
    }

    state vgrProdToFeed: VGRPickTokenFromProducerAndPlace {
        in vgr = vgrPickProducer;
        in tokenProducer = tokenProd;

        in pickFromProducerPosition {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1420.10;
            attribute :>> rot = 276.07;
        }
        in placePosition {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 959.56;
            attribute :>> rot = 2767.71;
        }
    }

    state vgrPickToSort: VGRPickTokenFromCBAndPlace {
        in vgr = vgrPlaceSorting;
        in cb = cbTransport;

        in pickFromCBPosition {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1179.45;
            attribute :>> rot = 1652.52;
        }
        in placePosition {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1606.50;
            attribute :>> rot = 0.00;
        }
    }

    state vgrMissionFeedTrans: VGRMissionWith2CB {
        /* Parts involved in this mission*/
        in vgrOne = vgrTransToFeeder;
        in feederCB = cbFeeder;
        in transportCB = cbTransport;

        /* parameters for some VGR actions*/        
        in pickFromFeederPosition {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1512.0;
            attribute :>> rot = 1440.0;
        }
        in placeToTransportPosition {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1512.0;
            attribute :>> rot = 720.0;
        }
    }

    state slMission: SortingLineSimpleMission {
        in sortingLine = slMachine;
        in vacuumGripper = vgrPlaceDepo;

        in whiteTokenPickup {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 858.66;
            attribute :>> rot = 2395.81;
        }
        in whiteTokenPlacement {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 247.01;
            attribute :>> rot = 643.04;
        }

        in blueTokenPickup {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 535.73;
            attribute :>> rot = 2166.64;
        }
        in blueTokenPlacement {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1493.20;
            attribute :>> rot = 291.27;
        }

        in redTokenPickup {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1618.86;
            attribute :>> rot = 2545.09;
        }
        in redTokenPlacement {
            attribute :>> vertical = 0.0;
            attribute :>> horizontal = 1012.68;
            attribute :>> rot = 1083.85;
        }
    }

}