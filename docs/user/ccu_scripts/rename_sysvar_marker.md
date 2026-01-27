# Rename System Variable Marker (hahm → HAHM)

This CCU script updates system variable description markers from lowercase `hahm` to uppercase `HAHM`.

## Background

The integration uses markers in system variable descriptions to identify variables that should be synchronized with Home Assistant. This script updates the marker format for consistency.

## Instructions

1. Open your CCU web interface
2. Navigate to **Programs and Connections** → **Programs**
3. Click **Test script** (Skript testen)
4. Paste the script below
5. Click **Execute** (Ausführen)

## Script

```
!- Search and replace in SysVar descriptions
string sSuchen   = "hahm";
string sErsetzen = "HAHM";

string sSV_ID;
foreach(sSV_ID, dom.GetObject(ID_SYSTEM_VARIABLES).EnumIDs()) {
  object oSV = dom.GetObject(sSV_ID);
  string sBeschreibung = oSV.DPInfo();
  if (sBeschreibung.Contains(sSuchen)) {
    sBeschreibung = sBeschreibung.Replace(sSuchen, sErsetzen);
    oSV.DPInfo(sBeschreibung);
    WriteLine(oSV.Name() #" | "# sSuchen #" replaced with: "# sErsetzen);
  }
}
```

## What the Script Does

1. Iterates through all system variables (`ID_SYSTEM_VARIABLES`)
2. Reads each variable's description (`DPInfo()`)
3. Checks if the description contains `hahm`
4. If found, replaces it with `HAHM`
5. Outputs the variable name and confirmation for each change

## Example Output

```
Anwesenheit | hahm replaced with: HAHM
Heizung_Status | hahm replaced with: HAHM
```

## Notes

- This is a one-time migration script
- The script only modifies description fields, not variable values
- No restart required after running the script
