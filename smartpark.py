from picamera import PiCamera
from time import sleep
camera = PiCamera()
camera.rotation = 180
camera.resolution = (2592, 1944)
camera.framerate=15

import cv2

import requests
import json

from collections import OrderedDict
from PIL import Image, ImageFilter

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

cred = credentials.Certificate('./ServiceAccountKey.json')
default_app = firebase_admin.initialize_app(cred)
db = firestore.client()


import pyzbar.pyzbar as pyzbar
import csv
from collections import defaultdict

def isSlotStillAvailable(slot, reservationID):
    slotFound = False
    parkingLot = cv2.imread("./assets/lotCaseFull.png")

    decodedSlots = pyzbar.decode(parkingLot)
    for decodedObject in decodedSlots:
        if (decodedObject.type == "QRCODE"):
            decodedSlot = decodedObject.data
            decodedSlot = decodedSlot.decode("utf-8")
            if (decodedSlot == slot):
                slotFound = True
    
    if (slotFound):
        db.collection(u"reservation").document(document.id).update({
            u"reservationPenalty": True,
        })


def checkSlotAvailability(reservedSlot):
    slotFound = False
    parkingLotA = cv2.imread("./assets/lotCaseA.png")

    #read qr codes from lot A
    decodedSlotsA = pyzbar.decode(parkingLotA)
    for decodedObject in decodedSlotsA:
        if (decodedObject.type == "QRCODE"):
            decodedSlot = decodedObject.data
            decodedSlot = decodedSlot.decode("utf-8")
            if (decodedSlot == reservedSlot):
                slotFound = True
    if (slotFound):
        return ""
    else:
        #read qr codes from lot B
        parkingLotB = cv2.imread("./assets/lotCase6.png")
        decodedSlotsB = pyzbar.decode(parkingLotB)
        reallocatedSlot = decodedSlotsB[0].data
        reallocatedSlot = reallocatedSlot.decode("utf-8")
        
        return reallocatedSlot

def updateReservation(decodedPlate):
    #get reservation
    reservationDocs = db.collection(u"reservation").where(u"vehicleID", u"==", decodedPlate).where(u"reservationStatus", u">", 1).where(u"reservationStatus", u"<", 4).stream()
    for document in reservationDocs:
        reservationID = document.id
        reservation = document.to_dict()
        if (reservation["reservationStatus"] == 2):
            #user checks in
            freeSlot = checkSlotAvailability(reservation["parkingSlotID"])
            if (freeSlot == ""):
                db.collection(u"reservation").document(document.id).update({
                    u"reservationStatus": 3,
                    u"reservationCheckInTime": datetime.now()
                })
            else:
                db.collection(u"reservation").document(document.id).update({
                    u"reservationStatus": 3,
                    u"reservationSlotReallocation": freeSlot,
                    u"reservationCheckInTime": datetime.now()
                })
        if (reservation["reservationStatus"] == 3):
            #user checks out
            db.collection(u"reservation").document(document.id).update({
                u"reservationStatus": 7,
                u"reservationCheckOutTime": datetime.now()
            })
    sleep(60)
    isSlotStillAvailable(freeSlot, reservationID)
    

def licensePlateRecognition():
    #take snapshot
    camera.start_preview()
    sleep(5)
    camera.capture("./assets/car.jpeg")
    camera.stop_preview() 

    result = []
    path = "./assets/car.jpeg"
    regions = ["fr", "it"]
    apiKey = 'f5357db3ccffa1b9617f3947e8cb9e7504d209b6'

    with open(path, "rb") as fp:
        response = requests.post(
            'https://api.platerecognizer.com/v1/plate-reader/',
            files=dict(upload=fp),
            data=dict(regions=regions),
            headers={'Authorization': 'Token ' + apiKey}
        )
        result.append(response.json(object_pairs_hook=OrderedDict))
    
    data = json.dumps(result)
    resp = json.loads(data)[0]
    try:
        decodedPlate = resp["results"][0]["plate"]
        print(decodedPlate)
        updateReservation(decodedPlate)
        
    except:
        print("recognition failed")

def carDetection():
    apiURL = "http://192.168.100.23:5000/"
    requestURL = apiURL + '/api/carDetection'

    content_type = 'image/jpg'
    headers = {'content-type': content_type}

    #take snapshot
    camera.start_preview()
    sleep(5)
    camera.capture("./assets/car.jpg")
    camera.stop_preview() 

    image = cv2.imread("./assets/car.jpg")
    _, image_encoded = cv2.imencode('.jpg', image)
    response = requests.post(requestURL, data=image_encoded.tostring(), headers=headers)
    
    print(response.text)
    if (response.text == '{"result": "vehicle"}'):
        print("detected")
        licensePlateRecognition()

def main():
    carDetection()

if __name__ == '__main__':
    main()