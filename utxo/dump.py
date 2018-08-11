import csv
import os
import struct

from binascii import hexlify

import pycoin.key.Key as Key
from pycoin.encoding import a2b_hashed_base58

from utxo.chainstate import ldb_iter
from utxo.script import unwitness
from utxo.util import new_utxo_file, utxo_file_name
from blockdb import read_blockfile


def snap_utxos(bitcoind, bitcoind_datadir, stop_block):
    
    cmd = "{} -reindex-chainstate -datadir=\"{}\" -stopatheight={}".format(
        bitcoind, bitcoind_datadir, stop_block)
    print("cmd")
    print (cmd)
    print("running " + cmd)
    os.system(cmd)


def get_magic(network, coin):
    if network == "testnet":
        if coin == "zcl":
            return bytearray.fromhex('fa 1a f9 bf') #testnetZCLMagic
        elif coin == "bitcoin":
            return bytearray.fromhex('0b 11 09 07') #testnetBitcoinMagic
    elif network == "mainnet":
        if coin == "zcl":
            return bytearray.fromhex('24 e9 27 64') #mainnetZCLMagic
        elif coin == "bitcoin":
            return bytearray.fromhex('f9 be b4 d9') #mainnetBitcoinMagic
    assert 0, "The provided network or coin name aren't supported. Use the following network: 'mainnet' or 'testnet'; coin: 'zcl' or 'bitcoin' "


def dump_transactions(datadir, output_dir, file_size, convert_segwit, maxT, debug, file_num, z_address, network, coin, t_address):
    #get magic for the provided network and coin
    magic = get_magic(network, coin)
    fileNumber = file_num
    print "file_num: ", file_num
    print "fileNumber: ", fileNumber
    returnObject = {}
    globalTransactionCounter = 0 #keep track of total transaction 
    #keep track of created files

    #write regular utxo (t-transactions)
    if(t_address):
        returnObject = dump_utxos(datadir, output_dir, file_size, convert_segwit, maxT, debug, fileNumber)
        print "Total T-files written: \t%d " % returnObject['fileNumber']
        print  "utxo-{:05}.bin".format(fileNumber) + " - utxo-{:05}.bin".format(returnObject['fileNumber'])
    else:
        returnObject['fileNumber'] = fileNumber
        returnObject['globalTransactionCounter'] = 0
    
    if z_address:
        globalTransactionCounter = returnObject['globalTransactionCounter']
        fileNumber = int(returnObject['fileNumber'])
        returnObject = {}
        returnObject = dump_jointsplits(datadir, output_dir, file_size, maxT, globalTransactionCounter, fileNumber + 1, magic)
        
        print "Total Z-files written: \t%d " % (int(returnObject['fileNumber']) - int(fileNumber) + 1)
        print  "utxo-{:05}.bin".format(fileNumber) + " - utxo-{:05}.bin".format(returnObject['fileNumber'])

        globalTransactionCounter = returnObject['globalTransactionCounter']
        fileNumber = returnObject['fileNumber']
    else:
        globalTransactionCounter = returnObject['globalTransactionCounter']
        fileNumber = returnObject['fileNumber']

    print "Total T+Z written: \t%d " % globalTransactionCounter
    print "Total files created: \t", fileNumber - file_num + 1
    print("##########################################")
    return


def dump_jointsplits(datadir, output_dir, n, maxT, globalTransactionCounter, fileNumber, magic):
    transaction = 0 #keep track of transcations per file
    transactionTotal = 0
    numberOfFilesToRead = 20
    blkFile = 0

    joinsplits = read_blockfile(datadir + "/blocks/blk" + '{0:0>5}'.format(blkFile) + ".dat", magic)
    while len(joinsplits) != 0:
        f = new_utxo_file(output_dir, fileNumber)  #create and open a new file
        for value in joinsplits:
            lengthStr = "{0:b}".format(len(value)) #bytes length of the transaction
            #format binary length in big-endian (32 bit) format
            if (len(lengthStr) < 32 ):
                while len(lengthStr) < 32:
                    lengthStr = "{0:b}".format(0) + lengthStr
            f.write(lengthStr) #write length of the transaction
            f.write(value)     #write actual transaction
            globalTransactionCounter += 1
            transaction += 1
            transactionTotal += 1
            if maxT != 0 and transaction >= maxT:
                break
        #remove objects from array that were written
        joinsplits = joinsplits[transaction:]
        transaction = 0
        if(len(joinsplits) == 0 and (blkFile <= numberOfFilesToRead)):
            try: 
                blkFile += 1
                joinsplits = read_blockfile(datadir + "/blocks/blk" + '{0:0>5}'.format(blkFile) + ".dat", magic)
            except IOError:
                print("Oops! File %s/blocks/blk0000%i.dat doesn't exist..." % (datadir, blkFile))
                break
        fileNumber += 1
        f.close()
    print("##########################################")
    print 'Total Z written: \t%s' % transactionTotal
    return { 'globalTransactionCounter': globalTransactionCounter, 'fileNumber': fileNumber }

def dump_utxos(datadir, output_dir, n, convert_segwit,
               maxT, debug, fileNum):
    # print("Starting to write Z-transactions")
    j = 0
    i = 0
    k = fileNum

    print('new file')
    f = new_utxo_file(output_dir, k)
    print('new_utxo_file path: ', f)

    for value in ldb_iter(datadir):
        tx_hash, height, index, amt, script = value
        
        if debug:
            print "Height: %d" % height
            print "Reversed: "
            reversedString = hexlify(tx_hash)
            print("".join(reversed([reversedString[x:x+2] for x in range(0, len(reversedString), 2)])))
            print ""

        if convert_segwit:
            script = unwitness(script, debug)

        # if debug:
        #     print(k, i, hexlify(tx_hash[::-1]), height, index,
        #           amt, hexlify(script))
        #     print(value)

        f.write(struct.pack('<QQ', amt, len(script)))
        f.write(script)
        f.write('\n')

        i += 1
        j += 1
        if i >= maxT:
            f.close()
            k += 1
            i = 0
            f = new_utxo_file(output_dir, k)

    f.close()
    print("##########################################")
    print("Total T written: \t%d" % j)
    print("##########################################")
    return { 'globalTransactionCounter': j, 'fileNumber': k }

