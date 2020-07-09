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

import numpy as np
import pyzbar.pyzbar as pyzbar
import csv
from collections import defaultdict

def monitorSlot():
    availableSlots = []
    allSlots = []

    img = cv2.imread("./assets/lotCaseA.png")

    decodedSlots = pyzbar.decode(img)
    for decodedSlot in decodedSlots:
        if (decodedSlot.type == "QRCODE"):
            slot = decodedSlot.data
            slot = slot.decode("utf-8")
            availableSlots.append(slot)
    
    parkingSlotDocs = db.collection(u"parkingSlot").stream()
    for document in parkingSlotDocs:
        allSlots.append(document.id)
    
    print(availableSlots)
    for slot in allSlots:
        if slot in availableSlots:
            db.collection(u"parkingSlot").document(slot).update({
                u"available": True
            })
        else:
            db.collection(u"parkingSlot").document(slot).update({
                u"available": False
            })           

def checkOut(reservationID):
    db.collection(u"reservation").document(reservationID).update({
            u"reservationStatus": 4,
            u"reservationCheckOutTime": firestore.firestore.SERVER_TIMESTAMP
        })

def checkSlotAvailability(parkingSlotID, parkingLot):
    slotFound = False
    img = cv2.imread(parkingLot)
    
    decodedSlots = pyzbar.decode(img)
    for decodedSlot in decodedSlots:
        if (decodedSlot.type == "QRCODE"):
            slot = decodedSlot.data
            slot = slot.decode("utf-8")
            if (slot == parkingSlotID):
                slotFound = True
    
    if (slotFound):
        return True
    else:
        return False
    
def checkIn(reservationID, parkingSlotID):
    slotAvailability = checkSlotAvailability(parkingSlotID, "./assets/emptyLot.png")
    if (slotAvailability):
        print("slot available")
        db.collection(u"reservation").document(reservationID).update({
            u"reservationStatus": 3,
            u"reservationCheckInTime": firestore.firestore.SERVER_TIMESTAMP
        })
        print("check slot")
        slotAvailability = checkSlotAvailability(parkingSlotID, "./assets/emptyLot.png")
        if (slotAvailability):
            db.collection(u"reservation").document(reservationID).update({
                u"reservationPenalty": True,
            })
    else:
        db.collection(u"reservation").document(reservationID).update({
            u"reservationSlotReallocation": True
        })

    

def checkReservation(licensePlate):
    licensePlate = licensePlate.upper()
    reservationDocs = db.collection(u"reservation").where(u"vehicleID", u"==", licensePlate).where(u"reservationStatus", u"<", 4).stream()
    for document in reservationDocs:
        reservationID = document.id
        reservation = document.to_dict()
        print(reservationID)
        if (((reservation["reservationStatus"] == 1) or (reservation["reservationStatus"] == 2)) and ((datetime.fromtimestamp(reservation["reservationStartTime"].timestamp()) < datetime.now()) and (datetime.fromtimestamp(reservation["reservationEndTime"].timestamp()) > datetime.now()))):
            print("check in")
            checkIn(reservationID, reservation["parkingSlotID"])
        else:
            if (reservation["reservationStatus"] == 3):
                checkOut(reservationID)
    print("monitor slot")
    monitorSlot()

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
        return decodedPlate
        
    except:
        return "None"

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
        return True
    else:
        return False

def main():
    carDetected = carDetection()
    if (carDetected):
        licensePlate = licensePlateRecognition()
        if (licensePlate != "None"):
            checkReservation(licensePlate)
    print("done")

if __name__ == '__main__':
    main()