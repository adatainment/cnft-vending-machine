from datetime import datetime
import os
import sys
import time
import traceback
from typing import Dict
import asset
import blockfrost
import cardanocli
import config
import data
import packtype
import payment
from utxo import Utxo
import vendingaddress

def vend(config_path: str):
    config.set_config_file(config_path)
    set_environment()

    vending_addresses = vendingaddress.get_vending_addresses()
    vending_to_packtypes_dict = {v.id: packtype.get_packtypes_dict(v) for v in vending_addresses}

    print(f"Vending addresses:\n{vending_addresses}")
    print(f"Packs for sale:\n{vending_to_packtypes_dict}")

    while True:
        try:
            for v in vending_addresses:
                utxos = cardanocli.get_utxos(v.address)
                for utxo in utxos:
                    process_utxo(utxo, v, vending_to_packtypes_dict[v.id])
        except:
            print(traceback.format_exc())

        time.sleep(5)

def process_utxo(utxo: Utxo, vending_address: vendingaddress.VendingAddress, lovelace_to_packtypes: Dict[int, packtype.PackType]):
    try:
        payment_addr = blockfrost.get_tx_payment_addr(utxo.tx_id)
        # get payment ID
        payment_id = data.get_payment_id(utxo.tx_id, utxo.index_id)
        if payment_id is None:
            payment_id = data.insert_payment(
                utxo.tx_id
                , utxo.index_id
                , utxo.lovelace.amount
                , utxo.other_assets
                , payment_addr
                , vending_address.id)
            print(f"Inserted new payment {payment_id} for {utxo.tx_id}#{utxo.index_id}")
        else:
            #TODO: Check if the payment is handled already. if so then continue to next tuxo
            return

        try:
            bought_pack = lovelace_to_packtypes.get(utxo.lovelace.amount)

            # handle incorrect payment amount
            if bought_pack is None:
                print(f"Payment {payment_id} did not submit a valid payment amount: {utxo.lovelace.amount}")
                tx_id = payment.return_payment(payment_id, payment_addr, vending_address, utxo)
                data.insert_payment_refund(payment_id, tx_id)
                return

            pack_id = data.get_pack_to_sell(bought_pack.pack_type_id)
            if pack_id is None:
                print(f"No more packs remaining: {bought_pack}")
                tx_id = payment.return_payment(payment_id, payment_addr, vending_address, utxo)
                data.insert_payment_refund(payment_id, tx_id)
                return

            data.update_pack_paymentid(pack_id, payment_id)
            tx_id = payment.send_pack(pack_id, payment_id, payment_addr, vending_address, utxo)
            data.update_pack_mintingtxid(pack_id, tx_id)
        except:
            #TODO: Log exception with payment
            print(traceback.format_exc())
            data.insert_error_log(payment_id, traceback.format_exc())
    except:
        # erroring here is unlikley but we don't want to block the utxo loop
        print(traceback.format_exc())

def set_environment():
    environment = config.config("environment")
    for key in environment:
        os.environ[key.upper()] = environment[key]

def update_print():
    old_f = sys.stdout
    class DebugWriter:
        def write(self, x):
            now = datetime.now().strftime("%H:%M:%S")
            old_f.write(x.replace("\n", " [%s]\n" % now))
    sys.stdout = DebugWriter()
