from typing import List
from asset import Asset
from itertools import groupby
import cardanocli
import config
import data
from nft import Nft, nft_to_asset
import os
import treasury
from utxo import Utxo
from vendingaddress import VendingAddress

#TODO return a payment result
def return_payment(payment_id: int, payment_addr: str, vending_address: VendingAddress, utxo: Utxo):
    print(f"Returning payment {payment_id} {utxo}")
    
    # define txn file paths
    pid = os.getpid()
    tx_draft_path = f"/tmp/txn_refund_{payment_id}_{pid}.draft"
    tx_raw_path = f"/tmp/txn_refund_{payment_id}_{pid}.raw"
    tx_signed_path = f"/tmp/txn_refund_{payment_id}_{pid}.signed"

    # calculate min ada for fees & refund utxo
    all_utxo_assets = [utxo.lovelace] + utxo.other_assets
    min_return_lovelace = cardanocli.calculate_min_value(payment_addr, all_utxo_assets)
    cardanocli.build_txn(
        utxo,
        [(payment_addr, all_utxo_assets)],
        0,
        tx_draft_path,
        None)
    min_fee = cardanocli.calculate_min_fee(tx_draft_path, 1, 1, 1)
    print(f"RETURN min fee {min_fee} min value {min_return_lovelace}")

    # if we don't have enough lovelace to process the transaction, stop
    if utxo.lovelace.amount < min_fee + min_return_lovelace:
        data.insert_insufficient_funds_for_return(payment_id, min_return_lovelace, min_fee)
        raise Exception(f"Not enough lovelace ({utxo.lovelace.amount}) to cover fees & min value ({min_fee}, {min_return_lovelace})")

    new_lovelace_output = Asset("lovelace", utxo.lovelace.amount - min_fee)
    cardanocli.build_txn(
        utxo,
        [(payment_addr, [new_lovelace_output] + utxo.other_assets)],
        min_fee,
        tx_raw_path,
        None)

    cardanocli.sign_txn(tx_raw_path, tx_signed_path, [vending_address.signing_key_path])
    tx_id = cardanocli.submit_txn(tx_signed_path)
    print(f"Payment {payment_id} refunded w/ txn {tx_id}.")

    return tx_id

def send_pack(pack_id: int, payment_id: int, payment_addr: str, vending_address: VendingAddress, utxo: Utxo):
    print(f"Sending pack {pack_id} for payment {payment_id}")

    # define txn file paths
    pid = os.getpid()
    tx_draft_path = f"/tmp/txn_mint_{payment_id}_{pid}.draft"
    tx_raw_path = f"/tmp/txn_mint_{payment_id}_{pid}.raw"
    tx_signed_path = f"/tmp/txn_mint_{payment_id}_{pid}.signed"
    tx_metadata_path = f"/tmp/txn_mint_{payment_id}_{pid}.json"

    treasuries = treasury.get_treasuries()

    # get packs
    pack_nfts = data.get_pack_nfts(pack_id)
    if len(pack_nfts) == 0:
        raise Exception(f"Pack {pack_id} has no NFTs assigned to it")

    # write metadata
    create_metadata_file(tx_metadata_path, pack_nfts)

    # calculate min ada for fees & pack utxo
    pack_assets = [nft_to_asset(n) for n in pack_nfts]
    min_send_lovelace = cardanocli.calculate_min_value(payment_addr, pack_assets)

    assets_to_send = [Asset("lovelace", min_send_lovelace)] + pack_assets
    vending_output = [(payment_addr, assets_to_send)]
    treasury_outputs = treasury.get_outputs(treasuries, utxo.lovelace.amount - min_send_lovelace)
    outputs = vending_output + treasury_outputs

    minting_skey_path = config.config("payment_keys")["minting_skey_path"]
    signing_keys = [vending_address.signing_key_path, minting_skey_path]
    mint_def = { 'assets': pack_assets, 'metadata_path': tx_metadata_path }
    print(f"Assets to send: {assets_to_send}") 
    cardanocli.build_txn(
        utxo,
        outputs,
        0,
        tx_draft_path,
        mint_def)
    min_fee = cardanocli.calculate_min_fee(tx_draft_path, 1, len(outputs), len(signing_keys))

    # setup transaction w/ proper fees & updated outputs
    treasury_outputs = treasury.get_outputs(treasuries, utxo.lovelace.amount - min_send_lovelace - min_fee)
    outputs = vending_output + treasury_outputs
    cardanocli.build_txn(
        utxo,
        outputs,
        min_fee,
        tx_raw_path,
        mint_def)

    cardanocli.sign_txn(tx_raw_path, tx_signed_path, signing_keys)
    tx_id = cardanocli.submit_txn(tx_signed_path)
    print(f"Payment {payment_id} sent pack {pack_id} w/ txn {tx_id}.")

    return tx_id

def create_metadata_file(path: str, nfts: List[Nft]):
    with open(path, 'w') as metadata_file:
        metadata_file.write(f"""{{
            \"721\": {{""")
        
        for policy_id, assets in groupby(nfts, lambda n: n.policy_id):
            metadata_file.write(f"\"{nfts[0].policy_id}\": {{")
            entries = []
            for asset_name, ns in groupby(assets, lambda n: n.asset_name):
                n = list(ns)[0]
                entries.append(f"\"{n.asset_name}\": {n.metadata_json}\n")
            metadata_file.write(",".join(entries))
            metadata_file.write(f"}}")

        metadata_file.write(f"}} }}")
