Utilities for PartKeepr
=======================

This is a collection of scripts to enhance the PartKeepr experience. Some of the tools are very specific to my use cases and might need some modification.
Features include:

* Syncing component data with distributors
  * Supported distributors: TME, Mouser, Digi-Key, LCSC
  * Synced data: Manufacturer, product number, description, price, photo, parameters
* List parts without manufacturer entries
* Importing location entries from a CSV file (for some reason I could not get the integrated import to work, so I made this)
* Auto-generate labels with Code128 barcodes for every storage location
* Rename components based on their parameters (e.g. rename a resistor from its part number to a human-readable name like 100Ω 0.1W 0603)

## Barcode Client
Also included is a tool that handles scanning the auto-generated barcodes mentioned above and allows simple stock modification by scanning control barcodes (See management_barcodes.pdf).
This tool also supports connecting to a flipdot display using my own control board to display part name and stock as well as feedback about the stock modification you're making on the display. (I told you it's very specific)