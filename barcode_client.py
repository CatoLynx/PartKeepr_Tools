import argparse
import serial
import time

from pprint import pprint

from secrets import *
from partkeepr import PartKeepr
from flipdot import Flipdot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-sp", "--scanner-port", type=str, required=True, help="Serial port for the barcode scanner")
    parser.add_argument("-fp", "--flipdot-port", type=str, required=False, help="Serial port for flipdot display")
    parser.add_argument("-sb", "--scanner-baudrate", type=int, required=False, default=9600, help="Baud rate for the barcode scanner")
    parser.add_argument("-fb", "--flipdot-baudrate", type=int, required=False, default=57600, help="Baud rate for the flipdot display")
    args = parser.parse_args()
    
    pk = PartKeepr(PK_BASE_URL, PK_USERNAME, PK_PASSWORD)
    scanner = serial.Serial(args.scanner_port, baudrate=args.scanner_baudrate, timeout=1.0)
    
    if args.flipdot_port:
        display = Flipdot(args.flipdot_port, args.flipdot_baudrate, 126, 16)
    else:
        display = None
    
    current_part = None
    current_action = ""
    current_value_digits = ""
    
    display_timeout = 120
    display_last_refresh = 0
    display_idle = True
    
    while True:
        if display is not None and not display_idle and time.time() - display_last_refresh >= display_timeout:
            print("Clearing display")
            display.display_multiline_text("")
            display_idle = True
        
        code = scanner.read(scanner.inWaiting()).decode('ascii').rstrip("\r\n")
        if not code:
            time.sleep(0.1)
            continue
        print("Code scanned: {}".format(code))
        
        # P: Part ID
        if code.startswith("P"):
            part_id = code[1:]
            current_part = pk.get_part(part_id)
            current_action = ""
            current_value_digits = ""
            print("  Part Name: {}".format(current_part['name']))
            print("  Stock Level: {}".format(current_part['stockLevel']))
            if display:
                display.display_multiline_text("{}\nSTOCK: {}".format(current_part['name'], current_part['stockLevel']))
                display_last_refresh = time.time()
                display_idle = False
                display_timeout = 120
        
        # A: Action
        elif code.startswith("A"):
            if not current_part:
                print("  No part selected!")
                continue
            
            current_action = code[1:]
            current_value_digits = ""
            print("  Action: {}".format(current_action))
            if display:
                display.display_multiline_text("{}\nACT: {} VAL: {}".format(current_part['name'], current_action, current_value_digits))
                display_last_refresh = time.time()
                display_idle = False
                display_timeout = 120
        
        # V: Value
        elif code.startswith("V"):
            if not current_part or not current_action:
                print("  No part or action selected!")
                continue
            
            value_digit = code[1:]
            print("  Value digit: {}".format(value_digit))
            current_value_digits += value_digit
            if display:
                display.display_multiline_text("{}\nACT: {} VAL: {}".format(current_part['name'], current_action, current_value_digits))
                display_last_refresh = time.time()
                display_idle = False
                display_timeout = 120
        
        # C: Confirm
        elif code.startswith("C"):
            print("  * CONFIRM")
            if not current_part or not current_action or not current_value_digits:
                print("  No part, action or value selected!")
                continue
            
            value = int(current_value_digits)
            
            if current_action == "ADD":
                print("    Adding {} to stock".format(value))
                result = pk.part_add_stock(current_part['@id'], value)
                if '@id' not in result:
                    print("  Error updating part!")
                    if display:
                        display.display_multiline_text("{}\nERROR UPDATING PART".format(current_part['name']))
                        display_last_refresh = time.time()
                        display_idle = False
                        display_timeout = 5
                else:
                    print("    New stock level: {}".format(result['stockLevel']))
                    if display:
                        display.display_multiline_text("{}\nNEW STOCK: {}".format(current_part['name'], result['stockLevel']))
                        display_last_refresh = time.time()
                        display_idle = False
                        display_timeout = 5
            
            elif current_action == "SUB":
                print("    Subtracting {} from stock".format(value))
                result = pk.part_remove_stock(current_part['@id'], value)
                if '@id' not in result:
                    print("  Error updating part!")
                    if display:
                        display.display_multiline_text("{}\nERROR UPDATING PART".format(current_part['name']))
                        display_last_refresh = time.time()
                        display_idle = False
                        display_timeout = 5
                else:
                    print("    New stock level: {}".format(result['stockLevel']))
                    if display:
                        display.display_multiline_text("{}\nNEW STOCK: {}".format(current_part['name'], result['stockLevel']))
                        display_last_refresh = time.time()
                        display_idle = False
                        display_timeout = 5
            
            elif current_action == "SET":
                print("    Setting stock to {}".format(value))
                result = pk.part_set_stock(current_part['@id'], value)
                if '@id' not in result:
                    print("  Error updating part!")
                    if display:
                        display.display_multiline_text("{}\nERROR UPDATING PART".format(current_part['name']))
                        display_last_refresh = time.time()
                        display_idle = False
                        display_timeout = 5
                else:
                    print("    New stock level: {}".format(result['stockLevel']))
                    if display:
                        display.display_multiline_text("{}\nNEW STOCK: {}".format(current_part['name'], result['stockLevel']))
                        display_last_refresh = time.time()
                        display_idle = False
                        display_timeout = 5
            
            current_part = None
            current_action = ""
            current_value_digits = ""


if __name__ == "__main__":
    main()
