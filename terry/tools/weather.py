"""Weather tool - get current weather and forecasts."""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from . import BaseTool, tool_registry


class WeatherTool(BaseTool):
    """Get weather information for a location."""

    name = "weather"
    description = "Get current weather and forecast for a location."
    input_schema = {
        "type": "object",
        "properties": {
            "location": {
                "type": "string",
                "description": "City name or coordinates (e.g., 'Beijing', '40.7128,-74.0060')",
            },
            "forecast": {
                "type": "boolean",
                "description": "Include forecast (default: false, current only)",
                "default": False,
            },
        },
        "required": ["location"],
    }

    def __init__(self, workdir: Path | None = None):
        self.workdir = workdir or Path.cwd()
        self.api_key = os.environ.get("WEATHER_API_KEY") or os.environ.get("OPENWEATHERMAP_API_KEY")

    def execute(self, location: str, forecast: bool = False) -> str:
        """Get weather information.

        Args:
            location: City name or coordinates
            forecast: Include forecast

        Returns:
            Weather information
        """
        if not self.api_key:
            return (
                "Error: Weather API requires WEATHER_API_KEY or OPENWEATHERMAP_API_KEY\n"
                "Get a free API key at: https://openweathermap.org/api"
            )

        try:
            # Get current weather
            current = self._get_current_weather(location)
            if not current:
                return f"Error: Could not get weather for {location}"

            # Format current weather
            result = self._format_current(current)

            # Get forecast if requested
            if forecast:
                forecast_data = self._get_forecast(location)
                if forecast_data:
                    result += "\n\n" + self._format_forecast(forecast_data)

            return result

        except Exception as e:
            return f"Error: {e}"

    def _get_current_weather(self, location: str) -> dict | None:
        """Get current weather data.

        Args:
            location: Location string

        Returns:
            Weather data or None
        """
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location if "," not in location else None,
            "lat": location.split(",")[0] if "," in location else None,
            "lon": location.split(",")[1] if "," in location else None,
            "appid": self.api_key,
            "units": "metric",  # Use Celsius
        }

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception:
            return None

    def _get_forecast(self, location: str) -> list[dict] | None:
        """Get weather forecast.

        Args:
            location: Location string

        Returns:
            Forecast data or None
        """
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "q": location if "," not in location else None,
            "lat": location.split(",")[0] if "," in location else None,
            "lon": location.split(",")[1] if "," in location else None,
            "appid": self.api_key,
            "units": "metric",
            "cnt": 8,  # Next 24 hours (3-hour intervals)
        }

        params = {k: v for k, v in params.items() if v is not None}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("list", [])
        except Exception:
            return None

    def _format_current(self, data: dict) -> str:
        """Format current weather data.

        Args:
            data: Weather data

        Returns:
            Formatted string
        """
        city = data.get("name", "Unknown")
        country = data.get("sys", {}).get("country", "")
        location_str = f"{city}, {country}" if country else city

        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})

        temp = main.get("temp", 0)
        feels_like = main.get("feels_like", 0)
        humidity = main.get("humidity", 0)
        description = weather.get("description", "Unknown").title()
        icon = self._get_weather_icon(weather.get("main", ""))
        wind_speed = wind.get("speed", 0)

        result = (
            f"### {icon} Weather in {location_str}\n\n"
            f"**{description}**\n\n"
            f"🌡️ Temperature: {temp:.1f}°C (feels like {feels_like:.1f}°C)\n"
            f"💧 Humidity: {humidity}%\n"
            f"💨 Wind: {wind_speed:.1f} m/s\n"
        )

        # Add sunrise/sunset if available
        sys_data = data.get("sys", {})
        if "sunrise" in sys_data and "sunset" in sys_data:
            from datetime import datetime
            sunrise = datetime.fromtimestamp(sys_data["sunrise"]).strftime("%H:%M")
            sunset = datetime.fromtimestamp(sys_data["sunset"]).strftime("%H:%M")
            result += f"🌅 Sunrise: {sunrise} | 🌇 Sunset: {sunset}\n"

        return result

    def _format_forecast(self, forecast_list: list[dict]) -> str:
        """Format forecast data.

        Args:
            forecast_list: List of forecast data

        Returns:
            Formatted string
        """
        from datetime import datetime

        result = "### 📅 24-Hour Forecast\n\n"

        for item in forecast_list[:6]:  # Show next 18 hours
            dt = datetime.fromtimestamp(item["dt"])
            time_str = dt.strftime("%H:%M")

            main = item.get("main", {})
            weather = item.get("weather", [{}])[0]

            temp = main.get("temp", 0)
            description = weather.get("description", "Unknown").title()
            icon = self._get_weather_icon(weather.get("main", ""))

            result += f"**{time_str}** - {icon} {temp:.0f}°C, {description}\n"

        return result

    def _get_weather_icon(self, condition: str) -> str:
        """Get weather icon.

        Args:
            condition: Weather condition

        Returns:
            Icon emoji
        """
        icons = {
            "Clear": "☀️",
            "Clouds": "☁️",
            "Rain": "🌧️",
            "Drizzle": "🌦️",
            "Thunderstorm": "⛈️",
            "Snow": "❄️",
            "Mist": "🌫️",
            "Fog": "🌫️",
            "Haze": "🌫️",
        }
        return icons.get(condition, "🌤️")


# Auto-register
tool_registry.register(WeatherTool())
