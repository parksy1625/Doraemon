# Nebula Air 1 Mod

Community test build based on Nebula 3.8.1 for Nreal/XREAL Air 1.

## Status
- Version: v0.1-test
- Base: Nebula 3.8.1
- Target: Nreal/XREAL Air 1
- Android package: ai.nreal.nebula.universal
- Status: Experimental / not yet fully verified on-device

## What changed
- Air 1 / unsupported-device compatibility adjustments
- Existing NRSDK, USB/IMU, 3DoF and AR Space components preserved
- Repackaged as an installable XAPK test build

## Install
1. Remove the existing Nebula installation if signature conflicts occur.
2. Download the v0.1-test XAPK from GitHub Releases.
3. Install it with an XAPK/split-APK installer.
4. Connect XREAL/Nreal Air 1.
5. Test AR Space, head tracking, 3DoF and recenter.

## Warning
This is a test build. Installation and launch packaging are prepared, but full device validation (AR Space + Air 1 + 3DoF) is still pending.

## Release file
Expected asset name:

`Nebula_3.8.1_Air1_Mod_v0.1.xapk`

Do not mark this build stable until on-device testing succeeds.
