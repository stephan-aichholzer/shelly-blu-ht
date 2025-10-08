#!/usr/bin/env python3
"""
Thermostat Control Module
Handles thermostat configuration, state management, and switch control
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field, validator


# Configuration
SHELLY_IP = os.getenv("SHELLY_IP", "192.168.2.12")
SWITCH_ID = int(os.getenv("SWITCH_ID", "0"))
CONFIG_FILE = os.getenv("THERMOSTAT_CONFIG_FILE", "/data/thermostat_config.json")


# Enums
class ThermostatMode(str, Enum):
    AUTO = "AUTO"
    ECO = "ECO"
    ON = "ON"
    OFF = "OFF"


# Data models
class ThermostatConfig(BaseModel):
    target_temp: float = Field(22.0, ge=18.0, le=24.0, description="Target temperature for AUTO mode (18-24°C)")
    eco_temp: float = Field(18.0, ge=18.0, le=24.0, description="Target temperature for ECO mode (18-24°C)")
    mode: ThermostatMode = Field(ThermostatMode.AUTO, description="Operating mode: AUTO, ECO, ON, OFF")
    hysteresis: float = Field(0.5, ge=0.1, le=2.0, description="Temperature hysteresis in °C (symmetric)")
    min_on_time: int = Field(30, ge=1, le=120, description="Minimum ON time in minutes")
    min_off_time: int = Field(10, ge=1, le=120, description="Minimum OFF time in minutes")
    temp_sample_count: int = Field(3, ge=1, le=10, description="Number of temperature samples to average (reduces noise)")
    control_interval: int = Field(180, ge=60, le=600, description="Control loop interval in seconds (default: 180s/3min)")

    @validator('eco_temp')
    def eco_temp_must_be_valid(cls, v, values):
        if 'target_temp' in values and v > values['target_temp']:
            raise ValueError('eco_temp must be <= target_temp')
        return v


class ThermostatState(BaseModel):
    switch_on: bool = False
    last_switch_change: Optional[datetime] = None
    last_control_decision: Optional[str] = None


class ThermostatStatus(BaseModel):
    config: ThermostatConfig
    current_temp: Optional[float] = None
    all_temps: Dict[str, Optional[float]] = {}
    switch_state: bool
    active_target: float
    heating_needed: Optional[bool] = None
    reason: Optional[str] = None
    switch_locked_until: Optional[datetime] = None


class ThermostatManager:
    """Manages thermostat configuration and state"""

    def __init__(self):
        self.config_file = Path(CONFIG_FILE)
        self.config = self._load_config()
        self.state = self._load_state()

    def _load_config(self) -> ThermostatConfig:
        """Load configuration from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    return ThermostatConfig(**data.get('config', {}))
            except Exception as e:
                print(f"Error loading config: {e}, using defaults")
        return ThermostatConfig()

    def _load_state(self) -> ThermostatState:
        """Load state from file or create default"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    state_data = data.get('state', {})
                    # Convert ISO string to datetime
                    if state_data.get('last_switch_change'):
                        state_data['last_switch_change'] = datetime.fromisoformat(
                            state_data['last_switch_change'].replace('Z', '+00:00')
                        )
                    return ThermostatState(**state_data)
            except Exception as e:
                print(f"Error loading state: {e}, using defaults")
        return ThermostatState()

    def _save(self):
        """Save configuration and state to file"""
        try:
            # Create directory if it doesn't exist
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert state to dict and handle datetime
            state_dict = self.state.dict()
            if state_dict.get('last_switch_change'):
                state_dict['last_switch_change'] = state_dict['last_switch_change'].isoformat()

            data = {
                'config': self.config.dict(),
                'state': state_dict
            }

            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
            raise

    def get_config(self) -> ThermostatConfig:
        """Get current configuration"""
        return self.config

    def set_config(self, new_config: ThermostatConfig):
        """Update configuration"""
        self.config = new_config
        self._save()

    def get_state(self) -> ThermostatState:
        """Get current state"""
        return self.state

    def update_state(self, switch_on: bool, decision: Optional[str] = None):
        """Update state after switch change"""
        if switch_on != self.state.switch_on:
            self.state.last_switch_change = datetime.utcnow()
        self.state.switch_on = switch_on
        if decision:
            self.state.last_control_decision = decision
        self._save()


class ShellyController:
    """Controls Shelly Pro 2 switch"""

    def __init__(self, ip: str = SHELLY_IP, switch_id: int = SWITCH_ID):
        self.ip = ip
        self.switch_id = switch_id
        self.session = requests.Session()
        self.session.timeout = 5

    def get_switch_status(self) -> Dict:
        """Get current switch status from Shelly"""
        try:
            url = f"http://{self.ip}/rpc/Switch.GetStatus?id={self.switch_id}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error getting switch status: {e}")

    def set_switch(self, turn_on: bool) -> Dict:
        """Set switch state on Shelly"""
        try:
            url = f"http://{self.ip}/rpc/Switch.Set?id={self.switch_id}&on={str(turn_on).lower()}"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"Error setting switch: {e}")


def calculate_control_decision(
    current_temp: float,
    target_temp: float,
    hysteresis: float,
    current_switch_on: bool,
    last_switch_change: Optional[datetime],
    min_on_time: int,
    min_off_time: int
) -> tuple[bool, str]:
    """
    Calculate whether switch should be ON or OFF based on temperature and timing constraints

    Returns: (should_be_on, reason)
    """
    now = datetime.utcnow()

    # Calculate time since last switch change
    if last_switch_change:
        time_since_change = (now - last_switch_change).total_seconds() / 60  # minutes
    else:
        time_since_change = float('inf')  # No previous change, allow any action

    # Temperature thresholds
    turn_on_threshold = target_temp - hysteresis
    turn_off_threshold = target_temp + hysteresis

    # Check if we're in the deadband
    if turn_on_threshold <= current_temp < turn_off_threshold:
        # In deadband - maintain current state
        if current_switch_on:
            return current_switch_on, f"Temperature {current_temp:.1f}°C in deadband [{turn_on_threshold:.1f}°C - {turn_off_threshold:.1f}°C], maintaining ON (running {time_since_change:.0f}/{min_on_time}min)"
        else:
            return current_switch_on, f"Temperature {current_temp:.1f}°C in deadband [{turn_on_threshold:.1f}°C - {turn_off_threshold:.1f}°C], maintaining OFF (idle {time_since_change:.0f}/{min_off_time}min)"

    # Temperature is below turn-on threshold
    if current_temp < turn_on_threshold:
        if current_switch_on:
            return True, f"Heating: {current_temp:.1f}°C < {turn_on_threshold:.1f}°C (already ON, running {time_since_change:.0f}/{min_on_time}min)"
        else:
            # Want to turn ON, check min_off_time
            if time_since_change >= min_off_time:
                return True, f"Turning ON: {current_temp:.1f}°C < {turn_on_threshold:.1f}°C (OFF for {time_since_change:.0f}min >= {min_off_time}min)"
            else:
                remaining = min_off_time - time_since_change
                return False, f"Heating needed but locked OFF (idle {time_since_change:.0f}/{min_off_time}min, {remaining:.0f}min remaining)"

    # Temperature is at or above turn-off threshold
    if current_temp >= turn_off_threshold:
        if not current_switch_on:
            return False, f"Target reached: {current_temp:.1f}°C >= {turn_off_threshold:.1f}°C (already OFF, idle {time_since_change:.0f}/{min_off_time}min)"
        else:
            # Want to turn OFF, check min_on_time
            if time_since_change >= min_on_time:
                return False, f"Turning OFF: {current_temp:.1f}°C >= {turn_off_threshold:.1f}°C (ON for {time_since_change:.0f}min >= {min_on_time}min)"
            else:
                remaining = min_on_time - time_since_change
                return True, f"Target reached but locked ON (running {time_since_change:.0f}/{min_on_time}min, {remaining:.0f}min remaining)"

    # Should not reach here, but maintain current state as fallback
    return current_switch_on, f"Maintaining current state (unexpected condition)"


# Global instances
thermostat_manager = ThermostatManager()
shelly_controller = ShellyController()

# Control loop state for health monitoring
control_loop_state = {
    "running": False,
    "last_run": None,
    "last_error": None,
    "consecutive_errors": 0,
    "last_mode": None,  # Track mode changes
    "mode_action_done": False  # Track if mode entry action completed
}
