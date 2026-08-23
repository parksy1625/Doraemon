# DORA-001 Control Architecture

## Control stack

```text
Pilot / Test Command
        ↓
Position / Velocity Layer
        ↓
Attitude Target
        ↓
Attitude Controller
        ↓
Rate Controller
        ↓
Motor Mixer
        ↓
ESC / Propulsion
```

## Sensors

Primary:
- IMU gyro
- IMU accelerometer
- Barometer

Optional during later phases:
- GNSS
- Optical flow
- Range sensor

## First controller

The first prototype should use a proven flight-control stack rather than writing a complete flight controller from scratch. The project-specific work should initially focus on the mechanical layout, propulsion characterization, sensor integration and safe test harness.

## Failure handling

The system should detect:

- sensor timeout
- excessive attitude error
- low battery
- excessive temperature
- propulsion telemetry failure
- radio link loss

The response must be defined before flight testing.
