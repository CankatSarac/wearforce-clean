#!/usr/bin/env python3
"""
Test script for TTS service functionality.

Usage:
    python test_tts.py [--host localhost] [--port 8002]
"""

import argparse
import asyncio
import base64
import json
import sys
from pathlib import Path
from typing import Dict, Any

import httpx


class TTSServiceTester:
    """Test client for TTS service."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def test_health_check(self) -> Dict[str, Any]:
        """Test the health check endpoint."""
        print("Testing health check...")
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            print(f"✓ Health check: {'PASS' if result['success'] else 'FAIL'}")
            return result
        except Exception as exc:
            print(f"✗ Health check: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def test_service_info(self) -> Dict[str, Any]:
        """Test the service info endpoint."""
        print("Testing service info...")
        
        try:
            response = await self.client.get(f"{self.base_url}/info")
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            print(f"✓ Service info: {'PASS' if result['success'] else 'FAIL'}")
            return result
        except Exception as exc:
            print(f"✗ Service info: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def test_list_voices(self) -> Dict[str, Any]:
        """Test the list voices endpoint."""
        print("Testing list voices...")
        
        try:
            response = await self.client.get(f"{self.base_url}/voices")
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            
            if result["success"] and "voices" in result["response"]:
                voices_count = len(result["response"]["voices"])
                print(f"✓ List voices: PASS - Found {voices_count} voices")
                
                # Print voice details
                for voice in result["response"]["voices"][:3]:  # Show first 3
                    print(f"  - {voice['id']}: {voice['name']} ({voice['language']}, {voice['gender']})")
            else:
                print(f"✗ List voices: FAIL")
                
            return result
        except Exception as exc:
            print(f"✗ List voices: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def test_voice_statistics(self) -> Dict[str, Any]:
        """Test the voice statistics endpoint."""
        print("Testing voice statistics...")
        
        try:
            response = await self.client.get(f"{self.base_url}/voices/statistics")
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            
            if result["success"]:
                stats = result["response"]
                print(f"✓ Voice statistics: PASS")
                print(f"  - Total voices: {stats.get('total_voices', 0)}")
                print(f"  - Languages: {list(stats.get('languages', {}).keys())}")
                print(f"  - Custom voices: {stats.get('custom_voices', 0)}")
            else:
                print(f"✗ Voice statistics: FAIL")
                
            return result
        except Exception as exc:
            print(f"✗ Voice statistics: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def test_system_validation(self) -> Dict[str, Any]:
        """Test the system validation endpoint."""
        print("Testing system validation...")
        
        try:
            response = await self.client.get(f"{self.base_url}/system/validation")
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            
            if result["success"]:
                validation = result["response"]
                overall_status = validation.get("overall_status", "unknown")
                print(f"✓ System validation: PASS - Status: {overall_status}")
                
                # Show component status
                components = validation.get("components", {})
                for component, status in components.items():
                    if isinstance(status, dict):
                        health = status.get("healthy", False)
                        print(f"  - {component}: {'OK' if health else 'FAIL'}")
                    else:
                        print(f"  - {component}: {status}")
                        
                # Show errors/warnings
                errors = validation.get("errors", [])
                warnings = validation.get("warnings", [])
                
                if errors:
                    print(f"  Errors: {len(errors)}")
                    for error in errors[:2]:  # Show first 2
                        print(f"    - {error}")
                
                if warnings:
                    print(f"  Warnings: {len(warnings)}")
                    for warning in warnings[:2]:  # Show first 2
                        print(f"    - {warning}")
            else:
                print(f"✗ System validation: FAIL")
                
            return result
        except Exception as exc:
            print(f"✗ System validation: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def test_text_synthesis(self, text: str = "Hello, this is a test of the text-to-speech service.") -> Dict[str, Any]:
        """Test text-to-speech synthesis."""
        print(f"Testing TTS synthesis with text: '{text[:50]}...'")
        
        try:
            request_data = {
                "text": text,
                "voice": "en_US-lessac-high",  # Default voice
                "language": "en",
                "speed": 1.0,
                "pitch": 1.0,
                "volume": 1.0,
                "format": "wav",
                "sample_rate": 22050,
                "enable_streaming": False
            }
            
            response = await self.client.post(
                f"{self.base_url}/synthesize",
                json=request_data
            )
            
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            
            if result["success"]:
                tts_result = result["response"]
                duration = tts_result.get("duration", 0)
                processing_time = tts_result.get("processing_time", 0)
                audio_size = len(tts_result.get("audio_data", "")) * 3 // 4  # Approximate binary size
                
                print(f"✓ TTS synthesis: PASS")
                print(f"  - Duration: {duration:.2f}s")
                print(f"  - Processing time: {processing_time:.2f}s")
                print(f"  - Audio size: ~{audio_size} bytes")
                
                # Optionally save audio to file
                if "audio_data" in tts_result:
                    try:
                        audio_bytes = base64.b64decode(tts_result["audio_data"])
                        output_file = Path("test_output.wav")
                        output_file.write_bytes(audio_bytes)
                        print(f"  - Audio saved to: {output_file}")
                    except Exception as exc:
                        print(f"  - Could not save audio: {exc}")
            else:
                print(f"✗ TTS synthesis: FAIL")
                
            return result
        except Exception as exc:
            print(f"✗ TTS synthesis: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def test_turkish_synthesis(self) -> Dict[str, Any]:
        """Test Turkish TTS synthesis."""
        turkish_text = "Merhaba, bu Türkçe metin-konuşma servisinin bir testidir."
        print(f"Testing Turkish TTS synthesis...")
        
        try:
            request_data = {
                "text": turkish_text,
                "voice": "tr_TR-dfki-medium",
                "language": "tr",
                "speed": 1.0,
                "format": "wav",
                "sample_rate": 22050,
            }
            
            response = await self.client.post(
                f"{self.base_url}/synthesize",
                json=request_data
            )
            
            result = {
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "response": response.json() if response.status_code == 200 else response.text
            }
            
            if result["success"]:
                print(f"✓ Turkish TTS synthesis: PASS")
            else:
                print(f"✗ Turkish TTS synthesis: FAIL")
                # This might fail if Turkish voice model isn't available
                if "not found" in str(result.get("response", "")).lower():
                    print(f"  Note: Turkish voice model may not be installed")
                
            return result
        except Exception as exc:
            print(f"✗ Turkish TTS synthesis: FAIL - {exc}")
            return {"success": False, "error": str(exc)}
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return summary."""
        print(f"Running TTS Service Tests against {self.base_url}\\n")
        
        tests = [
            ("Health Check", self.test_health_check),
            ("Service Info", self.test_service_info),
            ("List Voices", self.test_list_voices),
            ("Voice Statistics", self.test_voice_statistics),
            ("System Validation", self.test_system_validation),
            ("English TTS", self.test_text_synthesis),
            ("Turkish TTS", self.test_turkish_synthesis),
        ]
        
        results = {}
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\\n--- {test_name} ---")
            try:
                result = await test_func()
                results[test_name] = result
                if result.get("success", False):
                    passed += 1
            except Exception as exc:
                print(f"Test '{test_name}' failed with exception: {exc}")
                results[test_name] = {"success": False, "error": str(exc)}
        
        print(f"\\n{'='*50}")
        print(f"Test Summary: {passed}/{total} tests passed")
        print(f"{'='*50}")
        
        # Show failed tests
        failed_tests = [name for name, result in results.items() if not result.get("success", False)]
        if failed_tests:
            print(f"\\nFailed tests:")
            for test_name in failed_tests:
                error = results[test_name].get("error", "Unknown error")
                print(f"  - {test_name}: {error}")
        
        return {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": total - passed,
            "success_rate": passed / total * 100,
            "results": results
        }
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(description="Test TTS Service")
    parser.add_argument("--host", default="localhost", help="TTS service host")
    parser.add_argument("--port", type=int, default=8002, help="TTS service port")
    parser.add_argument("--text", help="Custom text to synthesize")
    
    args = parser.parse_args()
    
    base_url = f"http://{args.host}:{args.port}"
    tester = TTSServiceTester(base_url)
    
    try:
        if args.text:
            # Test specific text
            result = await tester.test_text_synthesis(args.text)
            success = result.get("success", False)
            print(f"\\nCustom text synthesis: {'SUCCESS' if success else 'FAILED'}")
        else:
            # Run all tests
            summary = await tester.run_all_tests()
            
            # Exit with error code if tests failed
            if summary["failed_tests"] > 0:
                sys.exit(1)
                
    except KeyboardInterrupt:
        print("\\nTests interrupted by user")
    except Exception as exc:
        print(f"\\nTest execution failed: {exc}")
        sys.exit(1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())