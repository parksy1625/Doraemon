# DORA-001 Physics Model

## 1. Hover

For total mass `m`, gravitational force is:

`W = m g`

Hover requires the sum of upward thrust to approximately balance weight:

`ΣT ≈ m g`

For `n` identical propulsion units:

`T_unit,hover ≈ m g / n`

## 2. Thrust margin

Maximum thrust must exceed hover thrust so that the vehicle can climb and reject disturbances. The required margin is a design parameter to be determined from the vehicle mass, control authority, propulsion response and safety analysis.

## 3. Translational motion

A multirotor moves horizontally by tilting its net thrust vector. Therefore attitude control and thrust control are coupled.

Desired control chain:

`position/velocity command → attitude target → attitude controller → motor thrust commands`

## 4. Power

Approximate electrical power is a function of propulsion operating point:

`P_electric ≈ Σ P_motor + P_avionics + P_losses`

Actual values must come from motor/propeller test data rather than a generic efficiency assumption.

## 5. Test measurements

Record at minimum:

- total mass
- static thrust per propulsion unit
- current
- voltage
- electrical power
- RPM when available
- ESC temperature
- motor temperature
- battery temperature
- vibration
- flight-controller attitude error

These measurements become the input for the next design iteration.
