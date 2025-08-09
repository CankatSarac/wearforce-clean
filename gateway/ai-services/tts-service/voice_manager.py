"""Voice management for TTS service with Piper models."""

import json
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from shared.exceptions import ModelInferenceError, ResourceNotFoundError
from shared.models import VoiceInfo, Language
from shared.utils import run_in_executor

logger = structlog.get_logger(__name__)


class VoiceManager:
    """Manager for TTS voices and models."""
    
    def __init__(self, models_dir: str, cache_store=None):
        self.models_dir = Path(models_dir)
        self.cache_store = cache_store
        self.voices: Dict[str, VoiceInfo] = {}
        self.voice_models: Dict[str, Dict[str, str]] = {}  # voice_id -> {model_path, config_path}
        self.is_initialized = False
        
    async def initialize(self) -> None:
        """Initialize voice manager and load available voices."""
        try:
            logger.info("Initializing voice manager", models_dir=str(self.models_dir))
            
            # Create models directory if it doesn't exist
            self.models_dir.mkdir(parents=True, exist_ok=True)
            
            # Load voices from models directory
            await self._load_voices_from_directory()
            
            # Load default voices if none found
            if not self.voices:
                logger.warning("No voices found, loading default voices")
                await self._load_default_voices()
            
            self.is_initialized = True
            logger.info(
                "Voice manager initialized",
                voices_count=len(self.voices),
                voice_ids=list(self.voices.keys()),
            )
            
        except Exception as exc:
            logger.error("Failed to initialize voice manager", error=str(exc), exc_info=True)
            raise ModelInferenceError(f"Voice manager initialization failed: {str(exc)}", "voice_manager")
    
    async def health_check(self) -> bool:
        """Check if voice manager is healthy."""
        return self.is_initialized and len(self.voices) > 0
    
    async def list_voices(self) -> List[VoiceInfo]:
        """Get list of all available voices."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        return list(self.voices.values())
    
    async def get_voice_info(self, voice_id: str) -> Optional[VoiceInfo]:
        """Get information about a specific voice."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        return self.voices.get(voice_id)
    
    async def get_voice_model_path(self, voice_id: str) -> Optional[str]:
        """Get the model file path for a voice."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        if voice_id not in self.voice_models:
            logger.error("Voice not found", voice_id=voice_id)
            return None
        
        model_path = self.voice_models[voice_id].get("model_path")
        if not model_path or not Path(model_path).exists():
            logger.error("Voice model file not found", voice_id=voice_id, model_path=model_path)
            return None
        
        return model_path
    
    async def add_voice(
        self,
        voice_id: str,
        name: str,
        language: Language,
        gender: str,
        model_path: str,
        config_path: Optional[str] = None,
        description: Optional[str] = None,
        sample_rate: int = 22050,
        is_custom: bool = True,
    ) -> VoiceInfo:
        """Add a new voice to the manager."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        # Validate model file exists
        if not Path(model_path).exists():
            raise ResourceNotFoundError("voice model", model_path)
        
        # Create voice info
        voice_info = VoiceInfo(
            id=voice_id,
            name=name,
            language=language,
            gender=gender,
            description=description,
            sample_rate=sample_rate,
            is_custom=is_custom,
        )
        
        # Store voice info and model paths
        self.voices[voice_id] = voice_info
        self.voice_models[voice_id] = {
            "model_path": model_path,
            "config_path": config_path,
        }
        
        # Cache voice info if cache is available
        if self.cache_store:
            await self.cache_store.set(
                self.cache_store.cache_key("voice_info", voice_id),
                voice_info.dict(),
                ttl=3600,
            )
        
        logger.info("Added voice", voice_id=voice_id, name=name, language=language)
        return voice_info
    
    async def remove_voice(self, voice_id: str) -> bool:
        """Remove a voice from the manager."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        if voice_id not in self.voices:
            return False
        
        # Remove from memory
        del self.voices[voice_id]
        del self.voice_models[voice_id]
        
        # Remove from cache
        if self.cache_store:
            await self.cache_store.delete(
                self.cache_store.cache_key("voice_info", voice_id)
            )
        
        logger.info("Removed voice", voice_id=voice_id)
        return True
    
    async def get_voices_by_language(self, language: Language) -> List[VoiceInfo]:
        """Get all voices for a specific language."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        return [
            voice for voice in self.voices.values()
            if voice.language == language
        ]
    
    async def get_voices_by_gender(self, gender: str) -> List[VoiceInfo]:
        """Get all voices of a specific gender."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        return [
            voice for voice in self.voices.values()
            if voice.gender.lower() == gender.lower()
        ]
    
    async def _load_voices_from_directory(self) -> None:
        """Load voices from the models directory."""
        
        def _scan_directory():
            voices = []
            
            # Look for .onnx model files (Piper format)
            for model_file in self.models_dir.rglob("*.onnx"):
                try:
                    # Look for corresponding .json config file
                    config_file = model_file.with_suffix(".onnx.json")
                    
                    if config_file.exists():
                        # Load voice configuration
                        with open(config_file, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        
                        # Extract voice information
                        voice_id = model_file.stem
                        voice_info = self._parse_piper_config(voice_id, config, str(model_file))
                        
                        if voice_info:
                            voices.append((voice_id, voice_info, str(model_file), str(config_file)))
                    
                    else:
                        # Create basic voice info without config
                        voice_id = model_file.stem
                        voice_info = VoiceInfo(
                            id=voice_id,
                            name=voice_id.replace("_", " ").title(),
                            language=Language.ENGLISH,  # Default
                            gender="unknown",
                            description=f"Voice model: {voice_id}",
                            sample_rate=22050,
                            is_custom=False,
                        )
                        voices.append((voice_id, voice_info, str(model_file), None))
                
                except Exception as exc:
                    logger.warning(f"Failed to load voice {model_file}", error=str(exc))
                    continue
            
            return voices
        
        # Run directory scanning in executor
        voices = await run_in_executor(_scan_directory)
        
        # Add voices to manager
        for voice_id, voice_info, model_path, config_path in voices:
            self.voices[voice_id] = voice_info
            self.voice_models[voice_id] = {
                "model_path": model_path,
                "config_path": config_path,
            }
        
        logger.info(f"Loaded {len(voices)} voices from directory")
    
    def _parse_piper_config(self, voice_id: str, config: Dict[str, Any], model_path: str) -> Optional[VoiceInfo]:
        """Parse Piper voice configuration."""
        try:
            # Extract information from Piper config
            audio_config = config.get("audio", {})
            dataset_config = config.get("dataset", {})
            inference_config = config.get("inference", {})
            
            # Map language code to Language enum
            language_code = config.get("language", "en")
            language_map = {
                "en": Language.ENGLISH,
                "tr": Language.TURKISH,
                "es": Language.SPANISH,
                "fr": Language.FRENCH,
                "de": Language.GERMAN,
                "it": Language.ITALIAN,
                "pt": Language.PORTUGUESE,
                "ru": Language.RUSSIAN,
                "ja": Language.JAPANESE,
                "ko": Language.KOREAN,
                "zh": Language.CHINESE,
                "ar": Language.ARABIC,
            }
            language = language_map.get(language_code, Language.ENGLISH)
            
            # Extract voice metadata
            name = config.get("name", voice_id.replace("_", " ").title())
            description = config.get("description", f"Piper TTS voice: {name}")
            sample_rate = audio_config.get("sample_rate", 22050)
            
            # Try to determine gender from voice name or metadata
            gender = "unknown"
            name_lower = name.lower()
            if any(word in name_lower for word in ["female", "woman", "girl", "lady"]):
                gender = "female"
            elif any(word in name_lower for word in ["male", "man", "boy", "gentleman"]):
                gender = "male"
            elif "gender" in config:
                gender = config["gender"]
            
            return VoiceInfo(
                id=voice_id,
                name=name,
                language=language,
                gender=gender,
                description=description,
                sample_rate=sample_rate,
                is_custom=False,
            )
            
        except Exception as exc:
            logger.warning(f"Failed to parse Piper config for {voice_id}", error=str(exc))
            return None
    
    async def _load_default_voices(self) -> None:
        """Load default/built-in voices when no models are found."""
        # This creates placeholder voices that would need actual models to work
        default_voices = [
            # English voices
            {
                "id": "en_US-lessac-high",
                "name": "Lessac (English US, High Quality)",
                "language": Language.ENGLISH,
                "gender": "male",
                "description": "High quality English US male voice with clear pronunciation",
                "sample_rate": 22050,
            },
            {
                "id": "en_US-amy-medium",
                "name": "Amy (English US, Medium Quality)",
                "language": Language.ENGLISH,
                "gender": "female",
                "description": "Medium quality English US female voice, warm and friendly",
                "sample_rate": 22050,
            },
            {
                "id": "en_GB-northern_english_male-medium",
                "name": "Northern English Male",
                "language": Language.ENGLISH,
                "gender": "male",
                "description": "British English male voice with northern accent",
                "sample_rate": 22050,
            },
            {
                "id": "en_US-libritts-high",
                "name": "LibriTTS (English US, High Quality)",
                "language": Language.ENGLISH,
                "gender": "female",
                "description": "High quality English US female voice from LibriTTS dataset",
                "sample_rate": 22050,
            },
            # Turkish voices
            {
                "id": "tr_TR-dfki-medium",
                "name": "DFKI (Turkish, Medium Quality)",
                "language": Language.TURKISH,
                "gender": "female",
                "description": "Medium quality Turkish female voice from DFKI",
                "sample_rate": 22050,
            },
            {
                "id": "tr_TR-fgl-medium",
                "name": "FGL (Turkish, Medium Quality)",
                "language": Language.TURKISH,
                "gender": "male",
                "description": "Medium quality Turkish male voice",
                "sample_rate": 22050,
            },
            {
                "id": "tr_TR-fahrettin-medium",
                "name": "Fahrettin (Turkish, Medium Quality)",
                "language": Language.TURKISH,
                "gender": "male",
                "description": "Turkish male voice with natural intonation",
                "sample_rate": 22050,
            },
        ]
        
        for voice_data in default_voices:
            voice_info = VoiceInfo(
                id=voice_data["id"],
                name=voice_data["name"],
                language=voice_data["language"],
                gender=voice_data["gender"],
                description=voice_data["description"],
                sample_rate=voice_data["sample_rate"],
                is_custom=False,
            )
            
            self.voices[voice_data["id"]] = voice_info
            
            # Create placeholder model path (would need actual model files)
            model_path = str(self.models_dir / f"{voice_data['id']}.onnx")
            self.voice_models[voice_data["id"]] = {
                "model_path": model_path,
                "config_path": None,
            }
        
        logger.warning(
            "Loaded default voices (placeholder models)",
            count=len(default_voices),
            note="Download actual Piper models for functionality",
        )
    
    async def download_voice_model(
        self,
        voice_id: str,
        download_url: str,
        config_url: Optional[str] = None,
    ) -> bool:
        """Download a voice model from URL."""
        try:
            import httpx
            from pathlib import Path
            import tempfile
            import os
            
            logger.info(
                "Downloading voice model",
                voice_id=voice_id,
                download_url=download_url,
            )
            
            # Create target directory for the voice
            voice_dir = self.models_dir / voice_id
            voice_dir.mkdir(parents=True, exist_ok=True)
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Download model file
                model_response = await client.get(download_url)
                model_response.raise_for_status()
                
                # Save model file
                model_path = voice_dir / f"{voice_id}.onnx"
                with open(model_path, 'wb') as f:
                    f.write(model_response.content)
                
                logger.info("Model file downloaded", path=str(model_path), size=len(model_response.content))
                
                # Download config file if provided
                config_path = None
                if config_url:
                    config_response = await client.get(config_url)
                    config_response.raise_for_status()
                    
                    config_path = voice_dir / f"{voice_id}.onnx.json"
                    with open(config_path, 'wb') as f:
                        f.write(config_response.content)
                    
                    logger.info("Config file downloaded", path=str(config_path))
                
                # Validate downloaded files
                if not model_path.exists() or model_path.stat().st_size == 0:
                    raise ValueError("Downloaded model file is invalid")
                
                # Try to parse config if available
                voice_info = None
                if config_path and config_path.exists():
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                        voice_info = self._parse_piper_config(voice_id, config, str(model_path))
                    except Exception as exc:
                        logger.warning("Failed to parse downloaded config", error=str(exc))
                
                # Create basic voice info if config parsing failed
                if not voice_info:
                    voice_info = VoiceInfo(
                        id=voice_id,
                        name=voice_id.replace("_", " ").title(),
                        language=Language.ENGLISH,  # Default
                        gender="unknown",
                        description=f"Downloaded voice model: {voice_id}",
                        sample_rate=22050,
                        is_custom=True,
                    )
                
                # Register the voice
                self.voices[voice_id] = voice_info
                self.voice_models[voice_id] = {
                    "model_path": str(model_path),
                    "config_path": str(config_path) if config_path else None,
                }
                
                logger.info("Voice model downloaded and registered", voice_id=voice_id)
                return True
                
        except Exception as exc:
            logger.error("Failed to download voice model", voice_id=voice_id, error=str(exc), exc_info=True)
            
            # Cleanup on failure
            try:
                if voice_dir.exists():
                    import shutil
                    shutil.rmtree(voice_dir)
            except Exception:
                pass
            
            return False
    
    async def validate_voice_model(self, voice_id: str) -> Dict[str, Any]:
        """Validate a voice model and return status."""
        if voice_id not in self.voice_models:
            return {"valid": False, "error": "Voice not found"}
        
        model_path = self.voice_models[voice_id]["model_path"]
        config_path = self.voice_models[voice_id].get("config_path")
        
        validation_result = {
            "valid": True,
            "voice_id": voice_id,
            "model_exists": Path(model_path).exists() if model_path else False,
            "config_exists": Path(config_path).exists() if config_path else False,
            "model_size": 0,
            "errors": [],
        }
        
        # Check model file
        if not Path(model_path).exists():
            validation_result["valid"] = False
            validation_result["errors"].append(f"Model file not found: {model_path}")
        else:
            validation_result["model_size"] = Path(model_path).stat().st_size
        
        # Check config file if specified
        if config_path and not Path(config_path).exists():
            validation_result["errors"].append(f"Config file not found: {config_path}")
        
        return validation_result
    
    async def get_recommended_voices(self, language: Language, use_case: str = "general") -> List[VoiceInfo]:
        """Get recommended voices for a specific language and use case."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        # Get voices for the language
        language_voices = await self.get_voices_by_language(language)
        
        if not language_voices:
            return []
        
        # Apply use-case specific recommendations
        recommendations = []
        
        if use_case == "general":
            # Prefer high quality, then medium quality voices
            high_quality = [v for v in language_voices if "high" in v.name.lower()]
            medium_quality = [v for v in language_voices if "medium" in v.name.lower()]
            recommendations = high_quality + medium_quality
        
        elif use_case == "fast":
            # Prefer medium quality for faster synthesis
            medium_quality = [v for v in language_voices if "medium" in v.name.lower()]
            low_quality = [v for v in language_voices if "low" in v.name.lower()]
            recommendations = medium_quality + low_quality
        
        elif use_case == "quality":
            # Prefer high quality voices only
            recommendations = [v for v in language_voices if "high" in v.name.lower()]
            if not recommendations:
                recommendations = language_voices  # Fallback to all voices
        
        else:
            recommendations = language_voices
        
        # Limit to top 3 recommendations
        return recommendations[:3]
    
    async def get_voice_statistics(self) -> Dict[str, Any]:
        """Get statistics about available voices."""
        if not self.is_initialized:
            raise ModelInferenceError("Voice manager not initialized", "voice_manager")
        
        stats = {
            "total_voices": len(self.voices),
            "languages": {},
            "genders": {},
            "quality_levels": {},
            "custom_voices": 0,
            "sample_rates": {},
        }
        
        for voice in self.voices.values():
            # Language statistics
            lang_key = voice.language.value
            stats["languages"][lang_key] = stats["languages"].get(lang_key, 0) + 1
            
            # Gender statistics
            stats["genders"][voice.gender] = stats["genders"].get(voice.gender, 0) + 1
            
            # Quality level statistics (from name)
            if "high" in voice.name.lower():
                quality = "high"
            elif "medium" in voice.name.lower():
                quality = "medium"
            elif "low" in voice.name.lower():
                quality = "low"
            else:
                quality = "unknown"
            stats["quality_levels"][quality] = stats["quality_levels"].get(quality, 0) + 1
            
            # Custom voices count
            if voice.is_custom:
                stats["custom_voices"] += 1
            
            # Sample rate statistics
            sr_key = str(voice.sample_rate)
            stats["sample_rates"][sr_key] = stats["sample_rates"].get(sr_key, 0) + 1
        
        return stats
    
    async def cleanup(self) -> None:
        """Cleanup voice manager resources."""
        logger.info("Cleaning up voice manager")
        
        self.voices.clear()
        self.voice_models.clear()
        self.is_initialized = False
    
    async def reload_voices(self) -> None:
        """Reload all voices from the models directory."""
        logger.info("Reloading voices")
        
        # Clear current voices
        self.voices.clear()
        self.voice_models.clear()
        
        # Reload from directory
        await self._load_voices_from_directory()
        
        # Load defaults if still empty
        if not self.voices:
            await self._load_default_voices()
        
        logger.info("Voices reloaded", count=len(self.voices))
    
    async def export_voice_config(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Export voice configuration for backup or sharing."""
        if voice_id not in self.voices:
            return None
        
        voice_info = self.voices[voice_id]
        voice_model_info = self.voice_models[voice_id]
        
        return {
            "voice_info": voice_info.dict(),
            "model_info": voice_model_info,
            "export_timestamp": time.time(),
            "version": "1.0",
        }