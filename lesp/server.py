"""
LESP Server - Language Execution Server Protocol

A JSON-RPC based server for compiling and executing code using LipVM.
"""

import sys
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from backend.LipVM import LipVM
from backend.Execution import Execution


class LESPServer:
    """LESP protocol server for LipVM execution."""
    
    def __init__(self, default_language_module: str = "languages.minilogo"):
        """Initialize LESP server.
        
        Args:
            default_language_module: Default language module to use
        """
        self.logger = self._setup_logging()
        self.vm: Optional[LipVM] = None
        self.execution: Optional[Execution] = None
        self.language_module = default_language_module
        
        self.logger.info("=" * 60)
        self.logger.info(f"LESP Server starting at {datetime.now()}")
        self.logger.info(f"Default language module: {default_language_module}")
        self.logger.info("=" * 60)
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('lipvm-server.log'),
                logging.StreamHandler(sys.stderr)
            ]
        )
        return logging.getLogger(__name__)
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a single LESP request.
        
        Args:
            request: JSON-RPC request object
            
        Returns:
            Response dictionary
        """
        method = request.get('method')
        params = request.get('params', {})
        request_id = request.get('id')
        
        self.logger.info(f"Handling request: method={method}, id={request_id}")
        
        # Route to appropriate handler
        handlers = {
            'setLanguageModule': self._handle_set_language_module,
            'compile': self._handle_compile,
            'start': self._handle_start,
            'stepForward': self._handle_step_forward,
            'stepBackward': self._handle_step_backward,
            'getState': self._handle_get_state,
        }
        
        handler = handlers.get(method)
        if handler:
            try:
                response = handler(params)
                return response
            except Exception as e:
                self.logger.exception(f"Error handling {method}")
                return {'success': False, 'error': str(e)}
        else:
            self.logger.warning(f"Unknown method: {method}")
            return {'success': False, 'error': f'Unknown method: {method}'}
    
    def _handle_set_language_module(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle setLanguageModule request."""
        module = params.get('module', 'languages.minilogo')
        self.logger.debug(f"Setting language module to: {module}")
        
        self.language_module = module
        # Reset VM to use new language module
        self.vm = None
        self.execution = None
        
        self.logger.info(f"Language module changed to: {module}")
        return {'success': True, 'message': f'Language module set to {module}'}
    
    def _handle_compile(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle compile request."""
        code = params.get('code', '')
        self.logger.debug(f"Compiling code (length={len(code)})")
        
        # Initialize VM if not already done
        if self.vm is None:
            self.logger.info(f"Initializing LipVM with language module: {self.language_module}")
            try:
                self.vm = LipVM(self.language_module)
            except Exception as e:
                self.logger.error(f"Failed to initialize LipVM: {e}")
                return {'success': False, 'error': f'Failed to initialize LipVM: {str(e)}'}
        
        try:
            self.execution = self.vm.compile_code(code)
            self.logger.info("Compilation successful")
            return {'success': True, 'message': 'Code compiled'}
        except Exception as e:
            self.logger.error(f"Compilation failed: {e}")
            return {'success': False, 'error': f'Compilation failed: {str(e)}'}
    
    def _serialize_environment(self, env) -> Dict[str, Any]:
        """Serialize an environment object to a dictionary.
        
        Args:
            env: Environment object to serialize
            
        Returns:
            Dictionary representation of the environment
        """
        return {
            'ip': env.ip,
            'heap': env.heap,
            'globals': env.globals,
            'stack': list(env.stack._items) if hasattr(env.stack, '_items') else [],
            'currentLine': env.current_line
        }
    
    def _handle_start(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle start execution request."""
        if not self.execution:
            self.logger.error("No code compiled")
            return {'success': False, 'error': 'No code compiled'}
        
        self.logger.debug("Starting execution")
        self.execution.start()
        
        heap = self.execution.environment.heap
        position = self.execution.environment.ip
        current_line = self.execution.environment.current_line
        history = [self._serialize_environment(env) for env in self.execution.history]
        
        self.logger.info(f"Execution started: position={position}, line={current_line}, heap keys={list(heap.keys())}, history_length={len(history)}")
        return {
            'success': True,
            'heap': heap,
            'position': position,
            'currentLine': current_line,
            'history': history
        }
    
    def _handle_step_forward(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle step forward request."""
        if not self.execution:
            self.logger.error("No execution started")
            return {'success': False, 'error': 'No execution started'}
        
        self.logger.debug("Stepping forward")
        self.execution.step_forward()
        
        heap = self.execution.environment.heap
        position = self.execution.environment.ip
        current_line = self.execution.environment.current_line
        history = [self._serialize_environment(env) for env in self.execution.history]
        
        self.logger.info(f"Step forward: position={position}, line={current_line}, heap keys={list(heap.keys())}, history_length={len(history)}")
        return {
            'success': True,
            'heap': heap,
            'position': position,
            'currentLine': current_line,
            'history': history
        }
    
    def _handle_step_backward(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle step backward request."""
        if not self.execution:
            self.logger.error("No execution started")
            return {'success': False, 'error': 'No execution started'}
        
        self.logger.debug("Stepping backward")
        self.execution.step_backward()
        
        heap = self.execution.environment.heap
        position = self.execution.environment.ip
        current_line = self.execution.environment.current_line
        history = [self._serialize_environment(env) for env in self.execution.history]
        
        self.logger.info(f"Step backward: position={position}, line={current_line}, heap keys={list(heap.keys())}, history_length={len(history)}")
        return {
            'success': True,
            'heap': heap,
            'position': position,
            'currentLine': current_line,
            'history': history
        }
    
    def _handle_get_state(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get state request."""
        if not self.execution:
            self.logger.error("No execution started")
            return {'success': False, 'error': 'No execution started'}
        
        heap = self.execution.environment.heap
        position = self.execution.environment.ip
        current_line = self.execution.environment.current_line
        history = [self._serialize_environment(env) for env in self.execution.history]
        
        self.logger.debug(f"Getting state: position={position}, line={current_line}, heap keys={list(heap.keys())}, history_length={len(history)}")
        
        return {
            'success': True,
            'heap': heap,
            'position': position,
            'currentLine': current_line,
            'history': history
        }
    
    def run(self):
        """Run the LESP server main loop."""
        self.logger.info("LESP Server starting main loop")
        
        for line in sys.stdin:
            try:
                line = line.strip()
                self.logger.debug(f"Received raw input: {line}")
                
                request = json.loads(line)
                self.logger.info(f"Parsed request: {request}")
                
                response = self.handle_request(request)
                response['id'] = request.get('id')
                
                response_str = json.dumps(response)
                self.logger.debug(f"Sending response: {response_str}")
                print(response_str, flush=True)
                self.logger.info("Response sent successfully")
                
            except json.JSONDecodeError as e:
                error_msg = f"JSON decode error: {e}"
                self.logger.error(error_msg)
                print(json.dumps({'success': False, 'error': error_msg}), flush=True)
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                self.logger.exception(error_msg)
                print(json.dumps({'success': False, 'error': str(e)}), flush=True)


def main():
    """Main entry point for LESP server."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='LESP Server - Language Execution Server Protocol for LipVM'
    )
    parser.add_argument(
        '--language-module',
        default='languages.minilogo',
        help='Default language module to use (default: languages.minilogo)'
    )
    
    args = parser.parse_args()
    
    server = LESPServer(default_language_module=args.language_module)
    server.run()


if __name__ == '__main__':
    main()
