"""
Function calling support for LLM service with load balancing.

Features:
- OpenAI function calling format
- Function schema validation
- Tool execution and result handling
- Multi-model function calling
- Load balancing for function calls
- Function call result caching
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Union, AsyncIterator
from dataclasses import dataclass, field

import structlog
from pydantic import BaseModel, ValidationError as PydanticValidationError

from shared.database import RedisManager, CacheStore
from shared.exceptions import ValidationError
from shared.monitoring import get_metrics
from shared.models import ChatMessage, MessageRole

logger = structlog.get_logger(__name__)


class FunctionDefinition(BaseModel):
    """Function definition schema."""
    name: str
    description: str
    parameters: Dict[str, Any]
    required: List[str] = []


class FunctionCall(BaseModel):
    """Function call from LLM."""
    name: str
    arguments: str  # JSON string


class FunctionResult(BaseModel):
    """Function execution result."""
    name: str
    content: str
    success: bool = True
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class FunctionCallRequest:
    """Function call processing request."""
    model_name: str
    messages: List[ChatMessage]
    functions: List[FunctionDefinition]
    function_call: Optional[Union[str, Dict[str, str]]] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class FunctionCallProcessor:
    """Processes function calls with load balancing."""
    
    def __init__(
        self,
        engine_manager,
        redis_manager: Optional[RedisManager] = None,
        cache_ttl: int = 300,
    ):
        self.engine_manager = engine_manager
        self.redis_manager = redis_manager
        self.cache_store = CacheStore(redis_manager, default_ttl=cache_ttl) if redis_manager else None
        
        # Function execution registry
        self.function_registry: Dict[str, callable] = {}
        self.function_schemas: Dict[str, FunctionDefinition] = {}
        
        # Load balancing
        self.model_function_performance: Dict[str, Dict[str, List[float]]] = {}
        
        # Built-in functions
        self._register_builtin_functions()
    
    def register_function(
        self,
        name: str,
        function: callable,
        schema: FunctionDefinition,
    ) -> None:
        """Register a function for calling."""
        self.function_registry[name] = function
        self.function_schemas[name] = schema
        logger.info(f"Registered function: {name}")
    
    def unregister_function(self, name: str) -> None:
        """Unregister a function."""
        if name in self.function_registry:
            del self.function_registry[name]
        if name in self.function_schemas:
            del self.function_schemas[name]
        logger.info(f"Unregistered function: {name}")
    
    def list_functions(self) -> List[FunctionDefinition]:
        """List available functions."""
        return list(self.function_schemas.values())
    
    async def process_function_call_request(
        self,
        request: FunctionCallRequest,
    ) -> Dict[str, Any]:
        """Process a function calling request."""
        start_time = time.time()
        
        try:
            # Validate functions
            self._validate_functions(request.functions)
            
            # Select best model for function calling
            model_name = self._select_function_calling_model(
                request.model_name,
                request.functions,
            )
            
            # Convert messages and functions to prompt
            prompt = self._create_function_call_prompt(
                request.messages,
                request.functions,
                request.function_call,
            )
            
            # Generate response
            result = await self.engine_manager.generate(
                model_name=model_name,
                prompt=prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                top_p=0.9,
                stop=["<|endoftext|>", "\n\nUser:", "\n\nHuman:"],
            )
            
            # Parse function calls from response
            function_calls = self._parse_function_calls(result["text"])
            
            # Execute function calls
            function_results = []
            for func_call in function_calls:
                func_result = await self._execute_function_call(func_call)
                function_results.append(func_result)
            
            # Record performance
            processing_time = time.time() - start_time
            self._record_function_performance(model_name, function_calls, processing_time)
            
            # Create response
            response_message = self._create_function_response_message(
                result["text"],
                function_calls,
                function_results,
            )
            
            return {
                "model": model_name,
                "message": response_message,
                "function_calls": [fc.dict() for fc in function_calls],
                "function_results": [fr.dict() for fr in function_results],
                "usage": {
                    "prompt_tokens": result.get("prompt_tokens", 0),
                    "completion_tokens": result.get("completion_tokens", 0),
                    "total_tokens": result.get("prompt_tokens", 0) + result.get("completion_tokens", 0),
                },
                "processing_time": processing_time,
            }
            
        except Exception as e:
            logger.error("Function call processing failed", error=str(e))
            raise
    
    async def process_function_call_stream(
        self,
        request: FunctionCallRequest,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Process function calling request with streaming."""
        # For streaming, we need to handle function calls differently
        # This is a simplified implementation - real streaming function calls are complex
        
        model_name = self._select_function_calling_model(
            request.model_name,
            request.functions,
        )
        
        prompt = self._create_function_call_prompt(
            request.messages,
            request.functions,
            request.function_call,
        )
        
        accumulated_text = ""
        function_calls = []
        
        async for chunk in self.engine_manager.generate_stream(
            model_name=model_name,
            prompt=prompt,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stop=["<|endoftext|>", "\n\nUser:", "\n\nHuman:"],
        ):
            accumulated_text += chunk.get("text", "")
            
            # Try to parse function calls from accumulated text
            try:
                potential_calls = self._parse_function_calls(accumulated_text)
                
                # If we found new function calls, execute them
                new_calls = potential_calls[len(function_calls):]
                for func_call in new_calls:
                    func_result = await self._execute_function_call(func_call)
                    function_calls.append(func_call)
                    
                    # Yield function call result
                    yield {
                        "type": "function_call",
                        "function_call": func_call.dict(),
                        "function_result": func_result.dict(),
                    }
            
            except Exception as e:
                logger.debug("Could not parse function calls yet", error=str(e))
            
            # Yield text chunk
            yield {
                "type": "text",
                "text": chunk.get("text", ""),
                "finish_reason": chunk.get("finish_reason"),
            }
    
    def _validate_functions(self, functions: List[FunctionDefinition]) -> None:
        """Validate function definitions."""
        for func_def in functions:
            try:
                # Validate function definition
                FunctionDefinition.parse_obj(func_def.dict())
                
                # Check if function is registered (if we have execution capability)
                if func_def.name not in self.function_registry:
                    logger.warning(f"Function {func_def.name} not registered for execution")
                
            except PydanticValidationError as e:
                raise ValidationError(f"Invalid function definition: {e}")
    
    def _select_function_calling_model(
        self,
        requested_model: str,
        functions: List[FunctionDefinition],
    ) -> str:
        """Select best model for function calling based on performance."""
        available_models = self.engine_manager.list_models()
        
        # If requested model is available, use it
        if requested_model in available_models:
            return requested_model
        
        # Otherwise, select based on function calling performance
        # For now, prefer larger models for function calling
        model_preferences = ["gpt-oss-120b", "gpt-oss-20b"]
        
        for model in model_preferences:
            if model in available_models:
                return model
        
        # Fallback to first available model
        return available_models[0] if available_models else "gpt-oss-20b"
    
    def _create_function_call_prompt(
        self,
        messages: List[ChatMessage],
        functions: List[FunctionDefinition],
        function_call: Optional[Union[str, Dict[str, str]]] = None,
    ) -> str:
        """Create prompt for function calling."""
        # System prompt for function calling
        system_prompt = """You are an AI assistant that can call functions to help answer questions.

Available functions:
"""
        
        # Add function descriptions
        for func in functions:
            system_prompt += f"\n{func.name}: {func.description}\n"
            system_prompt += f"Parameters: {json.dumps(func.parameters, indent=2)}\n"
        
        system_prompt += """

To call a function, use this format:
<function_call>
{"name": "function_name", "arguments": {"param1": "value1", "param2": "value2"}}
</function_call>

You can call multiple functions if needed. Always provide the function results in your response.
"""
        
        # Add function call preference
        if function_call:
            if isinstance(function_call, str):
                if function_call == "auto":
                    system_prompt += "\nCall functions when they would be helpful to answer the user's question."
                elif function_call == "none":
                    system_prompt += "\nDo not call any functions unless explicitly requested."
            elif isinstance(function_call, dict) and "name" in function_call:
                system_prompt += f"\nPrefer to use the {function_call['name']} function if applicable."
        
        # Convert messages to prompt
        prompt_parts = [system_prompt]
        
        for message in messages:
            if message.role == MessageRole.SYSTEM:
                prompt_parts.append(f"System: {message.content}")
            elif message.role == MessageRole.USER:
                prompt_parts.append(f"User: {message.content}")
            elif message.role == MessageRole.ASSISTANT:
                prompt_parts.append(f"Assistant: {message.content}")
            elif message.role == MessageRole.FUNCTION:
                prompt_parts.append(f"Function Result: {message.content}")
        
        prompt_parts.append("Assistant: I'll help you with that.")
        
        return "\n\n".join(prompt_parts)
    
    def _parse_function_calls(self, text: str) -> List[FunctionCall]:
        """Parse function calls from LLM response."""
        function_calls = []
        
        # Look for function call markers
        import re
        pattern = r'<function_call>\s*({.*?})\s*</function_call>'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                call_data = json.loads(match.strip())
                if "name" in call_data and "arguments" in call_data:
                    function_call = FunctionCall(
                        name=call_data["name"],
                        arguments=json.dumps(call_data["arguments"]),
                    )
                    function_calls.append(function_call)
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse function call: {match}", error=str(e))
        
        return function_calls
    
    async def _execute_function_call(self, function_call: FunctionCall) -> FunctionResult:
        """Execute a function call."""
        start_time = time.time()
        
        try:
            # Check if function is registered
            if function_call.name not in self.function_registry:
                return FunctionResult(
                    name=function_call.name,
                    content="",
                    success=False,
                    error=f"Function {function_call.name} not found",
                    execution_time=time.time() - start_time,
                )
            
            # Parse arguments
            try:
                arguments = json.loads(function_call.arguments)
            except json.JSONDecodeError as e:
                return FunctionResult(
                    name=function_call.name,
                    content="",
                    success=False,
                    error=f"Invalid function arguments: {e}",
                    execution_time=time.time() - start_time,
                )
            
            # Execute function
            function = self.function_registry[function_call.name]
            
            # Check if function is async
            if asyncio.iscoroutinefunction(function):
                result = await function(**arguments)
            else:
                result = function(**arguments)
            
            # Convert result to string
            if isinstance(result, dict):
                content = json.dumps(result, indent=2)
            elif isinstance(result, (list, tuple)):
                content = json.dumps(list(result), indent=2)
            else:
                content = str(result)
            
            execution_time = time.time() - start_time
            
            return FunctionResult(
                name=function_call.name,
                content=content,
                success=True,
                execution_time=execution_time,
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"Function execution failed: {function_call.name}",
                error=str(e),
                arguments=function_call.arguments,
            )
            
            return FunctionResult(
                name=function_call.name,
                content="",
                success=False,
                error=str(e),
                execution_time=execution_time,
            )
    
    def _create_function_response_message(
        self,
        text: str,
        function_calls: List[FunctionCall],
        function_results: List[FunctionResult],
    ) -> ChatMessage:
        """Create response message with function call results."""
        # Clean up the text (remove function call markers)
        import re
        clean_text = re.sub(r'<function_call>.*?</function_call>', '', text, flags=re.DOTALL)
        clean_text = clean_text.strip()
        
        # Add function results to response
        if function_results:
            clean_text += "\n\nFunction Results:\n"
            for result in function_results:
                if result.success:
                    clean_text += f"\n{result.name}: {result.content}"
                else:
                    clean_text += f"\n{result.name}: Error - {result.error}"
        
        # Create function call data
        function_call_data = None
        if function_calls:
            # For OpenAI compatibility, use the first function call
            first_call = function_calls[0]
            function_call_data = {
                "name": first_call.name,
                "arguments": first_call.arguments,
            }
        
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=clean_text,
            function_call=function_call_data,
        )
    
    def _record_function_performance(
        self,
        model_name: str,
        function_calls: List[FunctionCall],
        processing_time: float,
    ) -> None:
        """Record function calling performance for load balancing."""
        if model_name not in self.model_function_performance:
            self.model_function_performance[model_name] = {}
        
        for func_call in function_calls:
            func_name = func_call.name
            if func_name not in self.model_function_performance[model_name]:
                self.model_function_performance[model_name][func_name] = []
            
            # Keep last 100 performance records
            perf_list = self.model_function_performance[model_name][func_name]
            perf_list.append(processing_time)
            if len(perf_list) > 100:
                perf_list.pop(0)
    
    def _register_builtin_functions(self) -> None:
        """Register built-in utility functions."""
        
        def get_current_time() -> Dict[str, Any]:
            """Get the current date and time."""
            from datetime import datetime
            now = datetime.utcnow()
            return {
                "timestamp": now.timestamp(),
                "iso": now.isoformat(),
                "formatted": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        
        def calculate_math(expression: str) -> Dict[str, Any]:
            """Safely calculate a mathematical expression."""
            try:
                # Simple whitelist of allowed characters and functions
                import ast
                import operator
                import math
                
                # Allowed operations
                operators = {
                    ast.Add: operator.add,
                    ast.Sub: operator.sub,
                    ast.Mult: operator.mul,
                    ast.Div: operator.truediv,
                    ast.Pow: operator.pow,
                    ast.Mod: operator.mod,
                    ast.USub: operator.neg,
                }
                
                # Allowed functions
                functions = {
                    'abs': abs,
                    'round': round,
                    'min': min,
                    'max': max,
                    'sum': sum,
                    'sqrt': math.sqrt,
                    'sin': math.sin,
                    'cos': math.cos,
                    'tan': math.tan,
                    'log': math.log,
                    'exp': math.exp,
                }
                
                def eval_node(node):
                    if isinstance(node, ast.Num):
                        return node.n
                    elif isinstance(node, ast.Name):
                        if node.id in functions:
                            return functions[node.id]
                        else:
                            raise ValueError(f"Unknown name: {node.id}")
                    elif isinstance(node, ast.BinOp):
                        return operators[type(node.op)](eval_node(node.left), eval_node(node.right))
                    elif isinstance(node, ast.UnaryOp):
                        return operators[type(node.op)](eval_node(node.operand))
                    elif isinstance(node, ast.Call):
                        func = eval_node(node.func)
                        args = [eval_node(arg) for arg in node.args]
                        return func(*args)
                    else:
                        raise ValueError(f"Unsupported operation: {type(node)}")
                
                tree = ast.parse(expression, mode='eval')
                result = eval_node(tree.body)
                
                return {
                    "expression": expression,
                    "result": result,
                    "success": True,
                }
                
            except Exception as e:
                return {
                    "expression": expression,
                    "result": None,
                    "success": False,
                    "error": str(e),
                }
        
        # Register built-in functions
        self.register_function(
            "get_current_time",
            get_current_time,
            FunctionDefinition(
                name="get_current_time",
                description="Get the current date and time in UTC",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                required=[],
            )
        )
        
        self.register_function(
            "calculate_math",
            calculate_math,
            FunctionDefinition(
                name="calculate_math",
                description="Calculate a mathematical expression safely",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to calculate",
                        }
                    },
                },
                required=["expression"],
            )
        )
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get function calling performance statistics."""
        stats = {}
        
        for model_name, functions in self.model_function_performance.items():
            model_stats = {}
            for func_name, times in functions.items():
                if times:
                    model_stats[func_name] = {
                        "call_count": len(times),
                        "avg_time": sum(times) / len(times),
                        "min_time": min(times),
                        "max_time": max(times),
                        "recent_avg": sum(times[-10:]) / min(len(times), 10),
                    }
            stats[model_name] = model_stats
        
        return stats