# Arctic Spa Integration for Home Assistant

Local control of your [Arctic Spa](https://www.arcticspas.com/) hot tub directly from Home Assistant. No cloud, no API keys -- communicates directly with your spa over the local network.

## Features

- **Thermostat control** -- set and monitor water temperature
- **Pump control** -- turn pumps on/off with low/high speed support
- **Light control** -- toggle spa lights
- **Switch control** -- stereo, ozone, onzen, filter, exhaust fan, fogger
- **Sensors** -- water temperature, pH, ORP, heater status, filter status, power info
- **Dynamic entities** -- only creates entities for hardware that is actually installed in your spa
- **Energy saving** -- works great with [Tibber](https://tibber.com/) or [Nordpool](https://github.com/custom-components/nordpool) for price-based automations

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add `https://github.com/eivindcom/ha-arctic-spa` as an "Integration"
5. Search for "Arctic Spa" in HACS and install
6. Restart Home Assistant

### Manual

1. Download the `custom_components/arctic_spa` folder
2. Copy it to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "Arctic Spa"
3. Enter the local IP address of your spa (e.g. `192.168.1.244`)
4. The integration will connect and automatically detect your spa's hardware

## Important

**The spa only allows one TCP connection at a time.** Close the Arctic Spa mobile app before adding this integration. If the connection fails, make sure no other device is connected to the spa.

## Entities

Entities are created dynamically based on what hardware your spa reports:

| Entity | Type | Description |
|--------|------|-------------|
| Arctic Spa | Climate | Thermostat with current and target temperature |
| Pump 1-5 | Fan | Speed control (off/low/high) |
| Blower 1-2 | Fan | Speed control (off/low/high) |
| Light | Light | On/off control |
| Stereo | Switch | On/off control |
| Onzen | Switch | Water treatment system |
| Ozone | Switch | Ozone generator |
| Filter | Switch | Filtration system |
| Exhaust fan | Switch | Ventilation fan |
| Fogger | Switch | Fog machine |
| Eco mode | Switch | Lowers setpoint by 5°C to save energy |
| Onzen duration | Number | Salt cell run time (hours per day) |
| Water temperature | Sensor | Current water temperature (C) |
| Setpoint temperature | Sensor | Target temperature (C) |
| Heater 1/2 | Sensor | Heater status (idle/warmup/heating/cooldown) |
| Filter status | Sensor | Filter status (idle/filtering/purge/etc.) |
| Ozone status | Sensor | Ozone status (idle/active/suspended) |
| pH | Sensor | Water pH level |
| ORP | Sensor | Oxidation-Reduction Potential (mV) |
| Heater ADC | Sensor | Raw heater sensor value |
| Current ADC | Sensor | Raw current sensor value |
| Power phase | Sensor | Electrical phase configuration |
| Breaker size | Sensor | Circuit breaker rating (A) |
| Power | Sensor | Power consumption calculated from current sensor (kW) |

## Energy Saving with Tibber

The integration includes an **Eco mode** switch that lowers the setpoint by 5°C and restores it when turned off. Use this with Tibber to automatically save energy during expensive hours:

```yaml
automation:
  - alias: "Spa: Eco mode on during expensive electricity"
    trigger:
      - platform: numeric_state
        entity_id: sensor.electricity_price
        above: 2.0
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.arctic_spa_eco_mode

  - alias: "Spa: Eco mode off during cheap electricity"
    trigger:
      - platform: numeric_state
        entity_id: sensor.electricity_price
        below: 0.5
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.arctic_spa_eco_mode
```

You can also use `climate.set_temperature` directly for more precise control. The spa's insulation keeps the water warm for hours without heating, so this can significantly reduce electricity costs without affecting your spa experience.

The **Power** sensor (`sensor.arctic_spa_power`) shows real-time power consumption in kW, calculated from the spa's built-in current sensor.

## Protocol

This integration communicates with the spa using the proprietary Levven binary protocol over TCP port 65534. The protocol uses Protocol Buffers for message encoding. The protocol implementation was reverse-engineered by analyzing TCP traffic from the spa.

## Credits

- Created by [Eivind](https://github.com/eivindcom)
- Protocol inspired by [SPA Boii](https://github.com/Patrick-Ohlson/SpaBoii) by Patrick Ohlson

## License

MIT
