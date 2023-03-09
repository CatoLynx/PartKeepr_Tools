import argparse
import serial
import time

from pprint import pprint

from secrets import *
from tme import TME
from mouser import Mouser
from digikey import DigiKey
from lcsc import LCSC
from partkeepr import PartKeepr
from flipdot import Flipdot
from distributor_common import SUPPORTED_DISTRIBUTORS, get_part_data


# API ID of the default category and storage location for newly created parts
DEFAULT_CATEGORY = "/api/part_categories/1"
DEFAULT_STORAGE_LOCATION = "/api/storage_locations/11"


class BarcodeClient:
    def __init__(self, scanner_port, scanner_baudrate=9600, flipdot_port=None, flipdot_baudrate=57600):
        self.pk = PartKeepr(PK_BASE_URL, PK_USERNAME, PK_PASSWORD)
        self.tme = TME(TME_APP_KEY, TME_APP_SECRET)
        self.mouser = Mouser(MOUSER_API_KEY)
        self.digikey = DigiKey(DIGIKEY_CLIENT_ID, DIGIKEY_CLIENT_SECRET)
        self.lcsc = LCSC()
        
        self.scanner = serial.Serial(scanner_port, baudrate=scanner_baudrate, timeout=1.0)
        if flipdot_port:
            self.display = Flipdot(flipdot_port, flipdot_baudrate, 126, 16)
        else:
            self.display = None
        self.current_part = None
        self.current_action = ""
        self.current_value_digits = ""
        self.current_distributor = ""
        self.current_order_no = ""
        self.display_timeout = 300
        self.display_last_refresh = 0
        self.display_idle = True
        self.state = 'idle'
    
    def display_text(self, text, timeout):
        if not self.display:
            return
        self.display.display_multiline_text(text)
        self.display_last_refresh = time.time()
        self.display_idle = False
        self.display_timeout = timeout
    
    def display_part(self, part, timeout):
        print("  Part Name: {}".format(part['name']))
        print("  Stock Level: {}".format(part['stockLevel']))
        self.display_text("{}\nSTOCK: {} @ {}".format(part['name'], part['stockLevel'], part['storageLocation']['name']), timeout)
    
    def loop(self):
        while True:
            if self.display and not self.display_idle and time.time() - self.display_last_refresh >= self.display_timeout:
                print("Clearing display")
                self.display.display_multiline_text("")
                self.display_idle = True
                self.state = 'idle'
                self.current_part = None
                self.current_action = ""
                self.current_value_digits = ""
                self.current_distributor = ""
                self.current_order_no = ""
            
            code = self.scanner.read(self.scanner.inWaiting()).decode('ascii').rstrip("\r\n")
            if not code:
                time.sleep(0.1)
                continue
            print("Code scanned: {}".format(code))
            
            state_machine_done = False
            
            if not state_machine_done and self.state in ['idle', 'part_scanned', 'action_scanned', 'value_scanned']:
                # P: Part ID
                if code.startswith("P"):
                    part_id = code[1:]
                    self.state = 'part_scanned'
                    self.current_part = self.pk.get_part(part_id)
                    self.current_action = ""
                    self.current_value_digits = ""
                    self.current_distributor = ""
                    self.current_order_no = ""
                    self.display_part(self.current_part, 300)
                    state_machine_done = True
                
                # D: Expect distributor-specific code
                if code.startswith("D"):
                    self.state = 'distributor'
                    self.current_part = None
                    self.current_action = ""
                    self.current_value_digits = ""
                    self.current_distributor = code[1:]
                    self.current_order_no = ""
                    print("  Expect distributor-specific barcode: {}".format(self.current_distributor))
                    self.display_text("SCAN {} CODE".format(self.current_distributor), 300)
                    state_machine_done = True
            
            if not state_machine_done and self.state in ['part_scanned', 'action_scanned', 'value_scanned']:
                # A: Action
                if code.startswith("A"):
                    self.state = 'action_scanned'
                    self.current_action = code[1:]
                    self.current_value_digits = ""
                    print("  Action: {}".format(self.current_action))
                    self.display_text("{}\nACT: {} VAL: {}".format(self.current_part.get('name'), self.current_action, self.current_value_digits), 300)
                    state_machine_done = True
            
            if not state_machine_done and self.state in ['action_scanned', 'value_scanned']:
                # V: Value
                if code.startswith("V"):
                    value_digit = code[1:]
                    print("  Value digit: {}".format(value_digit))
                    self.state = 'value_scanned'
                    self.current_value_digits += value_digit
                    self.display_text("{}\nACT: {} VAL: {}".format(self.current_part.get('name'), self.current_action, self.current_value_digits), 300)
                    state_machine_done = True
            
            if not state_machine_done and self.state in ['value_scanned']:
                # C: Confirm
                if code == "C":
                    print("  * CONFIRM")
                    value = int(self.current_value_digits)
                    
                    if self.current_action == "ADD":
                        print("    Adding {} to stock".format(value))
                        result = self.pk.part_add_stock(self.current_part['@id'], value)
                        if '@id' not in result:
                            print("  Error updating part!")
                            self.display_text("{}\nERROR UPDATING PART".format(self.current_part.get('name')), 20)
                        else:
                            print("    New stock level: {}".format(result['stockLevel']))
                            self.display_text("{}\nNEW STOCK: {}".format(self.current_part.get('name'), result['stockLevel']), 20)
                    
                    elif self.current_action == "SUB":
                        print("    Subtracting {} from stock".format(value))
                        result = self.pk.part_remove_stock(self.current_part['@id'], value)
                        if '@id' not in result:
                            print("  Error updating part!")
                            self.display_text("{}\nERROR UPDATING PART".format(self.current_part.get('name')), 20)
                        else:
                            print("    New stock level: {}".format(result['stockLevel']))
                            self.display_text("{}\nNEW STOCK: {}".format(self.current_part.get('name'), result['stockLevel']), 20)
                    
                    elif self.current_action == "SET":
                        print("    Setting stock to {}".format(value))
                        result = self.pk.part_set_stock(self.current_part['@id'], value)
                        if '@id' not in result:
                            print("  Error updating part!")
                            self.display_text("{}\nERROR UPDATING PART".format(self.current_part.get('name')), 20)
                        else:
                            print("    New stock level: {}".format(result['stockLevel']))
                            self.display_text("{}\nNEW STOCK: {}".format(self.current_part.get('name'), result['stockLevel']), 20)
                    
                    self.state = 'idle'
                    self.current_part = None
                    self.current_action = ""
                    self.current_value_digits = ""
                    state_machine_done = True
            
            if not state_machine_done and self.state in ['distributor']:
                if self.current_distributor in SUPPORTED_DISTRIBUTORS:
                    self.current_order_no = code
                    parts = self.pk.get_parts(filter={"property": "distributors.orderNumber", "operator": "=", "value": code})
                    if len(parts) > 1:
                        print("  Ambiguous order number!")
                        print("  Found parts:")
                        print("\n".join(["    " + part['name'] for part in parts]))
                        self.display_text("{}\nAMBIGUOUS ORDER NO".format(code), 20)
                        self.state = 'idle'
                        self.current_distributor = ""
                    elif len(parts) == 0:
                        print("  Part not found!")
                        self.display_text("{}\nNOT FOUND. CREATE NEW?".format(code), 300)
                        self.state = 'create_new_part_question'
                    else:
                        self.state = 'part_scanned'
                        self.current_part = parts[0]
                        self.current_distributor = ""
                        self.current_order_no = ""
                        self.display_part(self.current_part, 300)
                else:
                    self.state = 'idle'
                    self.current_distributor = ""
                state_machine_done = True
            
            if not state_machine_done and self.state in ['create_new_part_question']:
                # Y: Yes
                if code == "Y":
                    if self.current_distributor in SUPPORTED_DISTRIBUTORS:
                        part_data = get_part_data(SUPPORTED_DISTRIBUTORS[self.current_distributor], self.current_order_no, self.tme, self.mouser, self.digikey, self.lcsc)
                        if part_data:
                            print("  Creating new part")
                            self.display_text("CREATING PART...", 20)
                            
                            print("Getting distributors")
                            distributors = self.pk.get_distributors()
                            dist_id = None
                            for dist in distributors:
                                if dist['name'] == SUPPORTED_DISTRIBUTORS[self.current_distributor]:
                                    dist_id = dist['@id']
                                    break
                            
                            print("Creating part distributor")
                            part_distributor_new = {
                                'distributor': {
                                    '@id': dist_id
                                },
                                'price': "0.00000",
                                'orderNumber': self.current_order_no
                            }
                            part_distributor = self.pk.create_part_distributor(part_distributor_new)
                            if '@id' not in part_distributor:
                                pprint(part_distributor)
                                print("Failed to create part distributor")
                                self.display_text("PART DIST CREATE FAIL", 20)
                                self.state = 'idle'
                                self.current_distributor = ""
                                self.current_order_no = ""
                                continue
                            
                            part_new = {
                                'name': part_data['manufacturer_part_no'],
                                'category': {
                                    '@id': DEFAULT_CATEGORY
                                },
                                'distributors': [
                                    {
                                        '@id': part_distributor['@id']
                                    }
                                ],
                                'storageLocation': {
                                    '@id': DEFAULT_STORAGE_LOCATION
                                }
                            }
                            part = self.pk.create_part(part_new)
                            if '@id' not in part:
                                pprint(part)
                                print("Failed to create part")
                                self.display_text("PART CREATE FAIL", 20)
                                self.state = 'idle'
                                self.current_distributor = ""
                                self.current_order_no = ""
                                continue
                                
                            part = self.pk.update_part_data(part, part_data, part['distributors'][0])
                            if '@id' not in part:
                                pprint(part)
                                print("Failed to update part")
                                self.display_text("PART UPDATE FAIL", 20)
                                self.state = 'idle'
                                self.current_distributor = ""
                                self.current_order_no = ""
                                continue
                            
                            self.state = 'part_scanned'
                            self.current_part = part
                            self.current_distributor = ""
                            self.current_order_no = ""
                            self.display_part(self.current_part, 300)
                        else:
                            print("Failed to get part data from {}".format(SUPPORTED_DISTRIBUTORS[self.current_distributor]))
                            self.display_text("PART DATA GET FAIL", 20)
                            self.state = 'idle'
                            self.current_distributor = ""
                            self.current_order_no = ""
                    else:
                        self.display_text("", 5)
                        self.state = 'idle'
                        self.current_distributor = ""
                        self.current_order_no = ""
                elif code == "N":
                    self.display_text("", 5)
                    self.state = 'idle'
                    self.current_distributor = ""
                    self.current_order_no = ""
                state_machine_done = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-sp", "--scanner-port", type=str, required=True, help="Serial port for the barcode scanner")
    parser.add_argument("-fp", "--flipdot-port", type=str, required=False, help="Serial port for flipdot display")
    parser.add_argument("-sb", "--scanner-baudrate", type=int, required=False, default=9600, help="Baud rate for the barcode scanner")
    parser.add_argument("-fb", "--flipdot-baudrate", type=int, required=False, default=57600, help="Baud rate for the flipdot display")
    args = parser.parse_args()
    
    client = BarcodeClient(args.scanner_port, args.scanner_baudrate, args.flipdot_port, args.flipdot_baudrate)
    client.loop()


if __name__ == "__main__":
    main()
