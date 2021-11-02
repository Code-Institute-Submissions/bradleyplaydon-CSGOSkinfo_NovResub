import os
from re import sub
import dateutil
from flask import (Flask, render_template,
                   request, redirect, url_for, flash, session)
from flask_pymongo import PyMongo
from flask_paginate import Pagination, get_page_args
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from dateutil import parser
import json
if os.path.exists("env.py"):
    import env


app = Flask(__name__)

app.config["MONGO_DBNAME"] = os.environ.get("MONGO_DBNAME")
app.config["MONGO_URI"] = os.environ.get("MONGO_URI")
app.secret_key = os.environ.get("SECRET_KEY")

mongo = PyMongo(app)

skinColl = mongo.db.skins


@app.route('/')
def index():
    latest_skins = skinColl.find().sort(
        ([("release_date", -1), ("rarity_precedence", -1)])).limit(17)
    return render_template(
        "pages/index.html", page_title="Latest Skins", skins=latest_skins)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        if existing_user:
            flash("Username already exists")
            return redirect(url_for("signup"))

        if request.form.get("password") != request.form.get("confirmpassword"):
            flash("Passwords doesn't match")
            return redirect(url_for("signup"))

        register = {
            "first_name": request.form.get("firstName").capitalize(),
            "last_name": request.form.get("lastName").capitalize(),
            "username": request.form.get("username").lower(),
            "email_address": request.form.get("email"),
            "password": generate_password_hash(request.form.get("password")),
            "is_admin": False,
            "skins_liked": list(),
            "skins_disliked": list()
        }

        mongo.db.users.insert_one(register)

        user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        skins_liked = list(map(str, user["skins_liked"]))
        skins_disliked = list(map(str, user["skins_disliked"]))

        session["user"] = {
                        "username": user["username"],
                        "is_admin": user["is_admin"],
                        "skins_liked": skins_liked,
                        "skins_disliked": skins_disliked}
        flash("Registration Succesful")
        return redirect(url_for("account",
                        username=session["user"]["username"]))

    return render_template(
        "components/auth.html", login=False, page_title="Sign Up")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        existing_user = mongo.db.users.find_one(
            {"username": request.form.get("username").lower()})

        skins_liked = list(map(str, existing_user["skins_liked"]))
        skins_disliked = list(map(str, existing_user["skins_disliked"]))
        if existing_user:
            if check_password_hash(existing_user["password"],
                                   request.form.get("password")):
                    session["user"] = {
                        "username": existing_user["username"],
                        "is_admin": existing_user["is_admin"],
                        "skins_liked": skins_liked,
                        "skins_disliked": skins_disliked}

                    flash("Welcome, {}".format(
                        request.form.get("username")))

                    return redirect(url_for(
                            "account", username=session["user"]["username"]))
            else:
                flash("Incorrect Username and/or Password")
                return redirect(url_for("login"))

        else:
            flash("Incorrect Username and/or Password")
            return redirect(url_for("login"))

    return render_template(
        "components/auth.html", login=True, page_title="Login")


@app.route("/logout")
def logout():
    flash("You have been logged out.")
    session.pop("user")
    return redirect(url_for("login"))


@app.route("/account/<username>", methods=["POST", "GET"])
def account(username):
    if session:
        skins_liked = list(map(ObjectId, session["user"]["skins_liked"]))
        skins_disliked = list(map(ObjectId, session["user"]["skins_disliked"]))

        weapon_liked = list(
            skinColl.find({"_id": {"$in": skins_liked}}))
        weapon_disliked = list(
            skinColl.find({"_id": {"$in": skins_disliked}}))

        return render_template(
            "pages/account.html", username=username,
            weapon_liked=weapon_liked, weapon_disliked=weapon_disliked)

    return redirect(url_for("index"))


@app.route("/about")
def about():
    return render_template("pages/about.html", page_title="About")


@app.route("/contact")
def contact():
    return render_template("pages/contact.html", page_title="Contact")


@app.route("/admin")
def admin():
    if session and session["user"]["is_admin"]:
        totalUsers = mongo.db.users.find().count()
        totalSkins = skinColl.count()
        totalAdmins = mongo.db.users.find({"is_admin": True}).count()
        skinUpVotes = skinColl.find({"up_votes": {"$gt": 0}})
        skinDownVotes = skinColl.find({"down_votes": {"$gt": 0}})
        totSkinUpVotes = 0
        totSkinDownVotes = 0
        highestLikes = skinColl.find_one(sort=[("up_votes", -1)])["up_votes"]
        mostLikedSkin = list(skinColl.find({"up_votes": highestLikes}))
        for skin in skinUpVotes:
            totSkinUpVotes = totSkinUpVotes + skin["up_votes"]

        for skin in skinDownVotes:
            totSkinDownVotes = totSkinDownVotes + skin["down_votes"]

        return render_template(
            "admin-pages/dashboard.html", page_title="Admin Dashboard",
            totalUsers=totalUsers, totalSkins=totalSkins,
            totalAdmins=totalAdmins, skinUpVotes=totSkinUpVotes,
            skinDownVotes=totSkinDownVotes, mostLikedSkin=mostLikedSkin)

    return render_template(
        "error-pages/404.html", page_title="404 Page Not Found")


@app.route('/view/skins', methods=["GET", "POST"])
def view_skins():
    if session and session["user"]["is_admin"]:
        return render_template(
            "admin-pages/view-skins.html", page_title="View Skins")
    return render_template("error-pages/404.html")


@app.route('/add/<skin_type>', methods=["GET", "POST"])
def add_skin(skin_type):
    if session and session["user"]["is_admin"]:
        weaponTypes = skinColl.distinct('weapon_type')
        weapons = {
            "pistol": skinColl.distinct("weapon_name",
                                        {"weapon_type": "Pistol"}),
            "rifle": skinColl.distinct("weapon_name",
                                       {"weapon_type": "Rifle"}),
            "heavy": skinColl.distinct("weapon_name",
                                       {"weapon_type": "Machinegun"}),
            "smg": skinColl.distinct("weapon_name",
                                     {"weapon_type": "SMG"}),
            "shotgun": skinColl.distinct("weapon_name",
                                         {"weapon_type": "Shotgun"}),
            "sniper rifle": skinColl.distinct("weapon_name",
                                              {"weapon_type": "Sniper Rifle"})
        }
        weaponRarities = skinColl.distinct('rarity')

        if skin_type == "weapon":
            return render_template(
                "components/forms/add-weapon.html", page_title="Add A Weapon",
                weaponTypes=weaponTypes, weapons=json.dumps(weapons),
                weaponRarities=weaponRarities)

        if skin_type == "knife":
            knifeTypes = skinColl.distinct('knife_type')
            return render_template(
                "components/forms/add-knife.html",
                page_title="Add A Knife", knifeTypes=knifeTypes)

        if skin_type == "gloves":
            return render_template(
                "components/forms/add-gloves.html", page_title="Add Gloves")

        if skin_type == "case":
            return render_template(
                "components/forms/add-cases.html", page_title="Add A Case")

        if skin_type == "sticker":
            stickerRarities = mongo.db.stickers.distinct('rarity')
            return render_template(
                "components/forms/add-stickers.html",
                page_title="Add A Sticker", stickerRarities=stickerRarities)

    return render_template("error-pages/404.html")


@app.route('/insert/<skin_type>', methods=["GET", "POST"])
def insert_skin(skin_type):
    if session and session["user"]["is_admin"]:
        imgDom = "https://community.cloudflare.steamstatic.com/economy/image/"
        if request.method == "POST":
            schema = get_skin_schema(skin_type)

            if skin_type == "knife":
                schema["release_date"] = parser.parse(
                    request.form.get("release-date"))
                skinColl.insert_one(schema)
                flash(f'{request.form.get("name")} Successfully Added')
                return redirect(url_for('add_skin', skin_type=skin_type))
            if skin_type == "weapon":
                schema["release_date"] = parser.parse(
                    request.form.get("release-date"))
                skinColl.insert_one(schema)
                flash(f'{request.form.get("name")} Successfully Added')
                return redirect(url_for('add_skin', skin_type=skin_type))
            if skin_type == "gloves":
                submit = {
                    "name": request.form.get("name"),
                    "skin_description": request.form.get("gloves_description"),
                    "type": "Gloves",
                    "rarity": "Extraordinary",
                    "conditions": {
                        "factory_new": True
                            if request.form.get("fn") else False,
                        "min_wear": True
                            if request.form.get("mw") else False,
                        "field_tested": True
                            if request.form.get("ft") else False,
                        "well_worn": True
                            if request.form.get("ww") else False,
                        "battle_scarred": True
                            if request.form.get("bs") else False
                    },
                    "image_urls": {
                        "factory_new": imgDom +
                        request.form.get("fnimage")
                        if request.form.get("fnimage") else None,
                        "min_wear": imgDom +
                        request.form.get("mwimage")
                        if request.form.get("mwimage") else None,
                        "field_tested": imgDom +
                        request.form.get("ftimage")
                        if request.form.get("ftimage") else None,
                        "well_worn": imgDom +
                        request.form.get("ftimage")
                        if request.form.get("wwimage") else None,
                        "battle_scarred": imgDom +
                        request.form.get("bsimage")
                        if request.form.get("bsimage") else None
                    },
                    "up_votes": 0,
                    "down_votes": 0
                }
                submit["release_date"] = parser.parse(
                    request.form.get("release-date"))
                skinColl.insert_one(submit)
                flash(f'{request.form.get("name")} Successfully Added')
                return redirect(url_for('add_skin', skin_type=skin_type))
            if skin_type == "case":
                submit = {
                    "name": request.form.get("name"),
                    "skin_description": request.form.get("case_description"),
                    "type": "Container",
                    "image_url": request.form.get("image"),
                    "up_votes": 0,
                    "down_votes": 0
                }
                submit["release_date"] = parser.parse(
                    request.form.get("release-date"))
                mongo.db.cases.insert_one(submit)
                flash(f'{request.form.get("name")} Successfully Added')
            if skin_type == "sticker":
                submit = {
                    "name": request.form.get("name"),
                    "skin_description":
                    request.form.get("sticker_description"),
                    "type": "Sticker",
                    "rarity": request.form.get("rarity"),
                    "image_url": request.form.get("image"),
                    "up_votes": 0,
                    "down_votes": 0
                }
                submit["release_date"] = parser.parse(
                    request.form.get("release-date"))
                mongo.db.stickers.insert_one(submit)
                flash(f'{request.form.get("name")} Successfully Added')
        return redirect(url_for('add_skin', skin_type=skin_type))
    return render_template("error-pages/404.html")


@app.route('/edit/skin', methods=["GET", "POST"])
def edit_skin():
    if session and session["user"]["is_admin"]:
        skins = list(skinColl.find({"weapon_type": {"$ne": "Knife"},
                     "type": {"$ne": "Gloves"}}))
        return render_template(
            "components/edit-skin.html", page_title="Edit A Skin",
            skins=skins)
    return render_template("error-pages/404.html")


@app.route('/edit/<skin_type>/<skin_id>', methods=["GET", "POST"])
def edit_selected_skin(skin_type, skin_id):
    if session and session["user"]["is_admin"]:
        if request.method == "POST":
            schema = get_skin_schema(skin_type)

            schema["release_date"] = parser.parse(
                request.form.get("release-date"))

            submit = schema
            if (skin_type == "weapon" or
               skin_type == "knife" or skin_type == "gloves"):
                up_votes = skinColl.find_one(
                    {"_id": ObjectId(skin_id)})["up_votes"]
                down_votes = skinColl.find_one(
                    {"_id": ObjectId(skin_id)})["down_votes"]
                schema["up_votes"] = up_votes
                schema["down_votes"] = down_votes
                skinColl.update({"_id": ObjectId(skin_id)}, submit)

            elif skin_type == "case":
                up_votes = mongo.db.cases.find_one(
                    {"_id": ObjectId(skin_id)})["up_votes"]
                down_votes = mongo.db.cases.find_one(
                    {"_id": ObjectId(skin_id)})["down_votes"]
                schema["type"] = "Container"
                schema["up_votes"] = up_votes
                schema["down_votes"] = down_votes
                mongo.db.cases.update({"_id": ObjectId(skin_id)}, submit)
            elif skin_type == "sticker":
                up_votes = mongo.db.stickers.find_one(
                    {"_id": ObjectId(skin_id)})["up_votes"]
                down_votes = mongo.db.stickers.find_one(
                    {"_id": ObjectId(skin_id)})["down_votes"]
                schema["up_votes"] = up_votes
                schema["down_votes"] = down_votes
                mongo.db.stickers.update({"_id": ObjectId(skin_id)}, submit)

            flash("The {} has been successfully updated".format(
                        request.form.get("name")))

        skin = skinColl.find_one({"_id": ObjectId(skin_id)})
        if skin_type == 'weapon':
            weaponTypes = skinColl.distinct('weapon_type')
            weaponRarities = skinColl.distinct('rarity')
            weapons = {
                "pistol": skinColl.distinct(
                    "weapon_name", {"weapon_type": "Pistol"}),
                "rifle": skinColl.distinct(
                    "weapon_name", {"weapon_type": "Rifle"}),
                "heavy": skinColl.distinct(
                    "weapon_name", {"weapon_type": "Machinegun"}),
                "smg": skinColl.distinct(
                    "weapon_name", {"weapon_type": "SMG"}),
                "shotgun": skinColl.distinct(
                    "weapon_name", {"weapon_type": "Shotgun"}),
                "sniper rifle": skinColl.distinct(
                    "weapon_name", {"weapon_type": "Sniper Rifle"})
            }
            return render_template(
                "components/edit-selected-skin.html", skin=skin,
                skin_type=skin_type, weaponTypes=weaponTypes,
                weapons=weapons, jsonweapons=json.dumps(weapons),
                weaponRarities=weaponRarities)
        elif skin_type == 'knife':
            knifeTypes = skinColl.distinct('knife_type')
            return render_template(
                "components/edit-selected-skin.html", skin=skin,
                skin_type=skin_type, knifeTypes=knifeTypes)
        elif skin_type == 'gloves':
            return render_template(
                "components/edit-selected-skin.html",
                skin=skin, skin_type=skin_type)
        elif skin_type == 'case':
            skin = mongo.db.cases.find_one({"_id": ObjectId(skin_id)})
            return render_template(
                "components/edit-selected-skin.html",
                skin=skin, skin_type=skin_type)
        elif skin_type == 'sticker':
            skin = mongo.db.stickers.find_one({"_id": ObjectId(skin_id)})
            stickerRarities = mongo.db.stickers.distinct('rarity')
            return render_template(
                "components/edit-selected-skin.html",
                skin=skin, skin_type=skin_type,
                stickerRarities=stickerRarities)
    return render_template("error-pages/404.html")


@app.route('/delete/skin', methods=["GET", "POST"])
def delete_skin():
    if session and session["user"]["is_admin"]:
        skins = list(skinColl.find({"weapon_type": {"$ne": "Knife"},
                     "type": {"$ne": "Gloves"}}))
        return render_template(
            "components/delete-skin.html", page_title="Delete A Skin",
            skins=skins)
    return render_template("error-pages/404.html")


@app.route('/delete/skin/<skin_id>', methods=["GET", "POST"])
def delete_selected_skin(skin_id):
    if session and session["user"]["is_admin"]:
        skinColl.remove({"_id": ObjectId(skin_id)}
                        ), flash("Skin has been successfully removed"
                                 ) if skinColl.find_one(
                                     {"_id": ObjectId(skin_id)}
                                     ) is not None else False
        mongo.db.cases.remove({"_id": ObjectId(skin_id)}
                              ), flash("Skin has been successfully removed"
                                       ) if mongo.db.cases.find_one(
                                           {"_id": ObjectId(skin_id)}
                                           ) is not None else False
        mongo.db.stickers.remove({"_id": ObjectId(skin_id)}
                                 ), flash("Skin has been successfully removed"
                                          ) if mongo.db.stickers.find_one(
                                              {"_id": ObjectId(skin_id)}
                                              ) is not None else False

        return redirect(url_for("admin"))
    return render_template("error-pages/404.html")


@app.route('/get/skin', methods=["GET", "POST"])
def get_skin_by_name():
    if session and session["user"]["is_admin"]:
        if request.method == "POST":
            reqJson = request.json
            skin_name = str(f'{reqJson["name"]}')

            skinExists = skinColl.find({"name": skin_name}).count()
            if skinExists > 0:
                return "True"
            else:
                return "False"

        if request.method == "GET":
            searchOptions = {}
            if ("searchweaponskin" in request.args and
                request.values["searchweaponskin"] is not None and
                    request.values["searchweaponskin"] != ''):
                searchOptions = {"weapon_type": {"$ne": "Knife"},
                                 "type": {"$ne": "Gloves"}}
                searchOptions["name"] = (
                    {"$regex": request.values["searchweaponskin"],
                     "$options": "i"})
                foundSkins = skinColl.find(
                    searchOptions).sort("rarity_precedence", -1)
                return render_template(
                    "components/edit-skin.html", page_title="Search Results",
                    foundSkins=foundSkins)

            if ("deleteweaponskins" in request.args and
                request.values["deleteweaponskins"] is not None and
                    request.values["deleteweaponskins"] != ''):
                searchOptions["name"] = (
                    {"$regex": request.values["deleteweaponskins"],
                     "$options": "i"})
                foundSkins = skinColl.find(searchOptions).sort(
                    "rarity_precedence", -1)
                cases = mongo.db.cases.find(searchOptions).sort(
                    "release_date", -1)
                stickers = mongo.db.stickers.find(searchOptions).sort(
                    "rarity_precedence", -1)
                return render_template(
                    "components/delete-skin.html", page_title="Delete Skins",
                    foundSkins=foundSkins, cases=cases, stickers=stickers)

            if ("searchknifes" in request.args and
                request.values["searchknifes"] is not None and
                    request.values["searchknifes"] != ''):
                searchOptions = {"weapon_type": {"$eq": "Knife"}}
                searchOptions["name"] = (
                    {"$regex": request.values["searchknifes"],
                     "$options": "i"})
                foundKnifes = skinColl.find(searchOptions).sort(
                    "rarity_precedence", -1)
                return render_template(
                    "components/edit-skin.html", page_title="Knife Results",
                    foundKnifes=foundKnifes)

            if ("searchcases" in request.args and
                request.values["searchcases"] is not None and
                    request.values["searchcases"] != ''):
                searchOptions = {"type": {"$eq": "Container"}}
                searchOptions["name"] = (
                    {"$regex": request.values["searchcases"],
                     "$options": "i"})
                foundCases = mongo.db.cases.find(searchOptions).sort(
                    "release_date", -1)
                return render_template(
                    "components/edit-skin.html", page_title="Edit Skin",
                    foundCases=foundCases)

            if ("searchstickers" in request.args and
                request.values["searchstickers"] is not None and
                    request.values["searchstickers"] != ''):
                searchOptions = {"type": {"$eq": "Sticker"}}
                searchOptions["name"] = (
                    {"$regex": request.values["searchstickers"],
                     "$options": "i"})
                foundStickers = mongo.db.stickers.find(searchOptions).sort(
                    "rarity_precedence", -1)
                return render_template(
                    "components/edit-skin.html", page_title="Sticker Results",
                    foundStickers=foundStickers)

            if ("searchgloves" in request.args and
                request.values["searchgloves"] is not None and
                    request.values["searchgloves"] != ''):
                searchOptions = {"type": {"$eq": "Gloves"}}
                searchOptions["name"] = (
                    {"$regex": request.values["searchgloves"],
                     "$options": "i"})
                foundGloves = skinColl.find(searchOptions).sort(
                    "release_date", -1)
                return render_template(
                    "components/edit-skin.html", page_title="Gloves Results",
                    foundGloves=foundGloves)

            if ("searchallskins" in request.args and
                request.values["searchallskins"] is not None and
                    request.values["searchallskins"] != ''):
                searchOptions["name"] = (
                    {"$regex": request.values["searchallskins"],
                     "$options": "i"})
                foundSkins = skinColl.find(searchOptions).sort(
                    "rarity_precedence", -1)
                cases = mongo.db.cases.find(searchOptions).sort(
                    "release_date", -1)
                stickers = mongo.db.stickers.find(searchOptions).sort(
                    "rarity_precedence", -1)
                if session and session["user"]["is_admin"]:
                    return render_template(
                        "admin-pages/view-skins.html",
                        page_title="View Skins", foundSkins=foundSkins,
                        cases=cases, stickers=stickers)
    searchOptions = {}

    if ("searchallskins" in request.args and
        request.values["searchallskins"] is not None and
            request.values["searchallskins"] != ''):
        searchOptions["name"] = (
                    {"$regex": request.values["searchallskins"],
                     "$options": "i"})
        foundSkins = skinColl.find(searchOptions).sort(
                    "rarity_precedence", -1)
        cases = mongo.db.cases.find(searchOptions).sort(
                    "release_date", -1)
        stickers = mongo.db.stickers.find(searchOptions).sort(
                    "rarity_precedence", -1)

    return render_template("pages/search-results.html",
                           page_title="Search Results", foundSkins=foundSkins,
                           cases=cases, stickers=stickers)


def get_skin_schema(skin_type):
    imgDom = "https://community.cloudflare.steamstatic.com/economy/image/"
    standard_schema = {
                "name": request.form.get("name"),
                "skin_description": request.form.get("skin_description"),
                "type": "Weapon",
                "weapon_type": request.form.get("weapon_type"),
                "weapon_name": request.form.get("weapon_name"),
                "rarity": request.form.get("rarity"),
                "rarity_precedence": (
                    6 if request.form.get("rarity") == "Contraband"
                    else 5 if request.form.get("rarity") == "Covert"
                    else 4 if request.form.get("rarity") == "Classified"
                    else 3 if request.form.get("rarity") == "Restricted"
                    else 2 if request.form.get("rarity") == "Mil-Spec Grade"
                    else 1 if request.form.get("rarity") == "Industrial Grade"
                    else 0 if request.form.get("rarity") == "Consumer Grade"
                    else ""),
                "souvenir_available": True if
                request.form.get("souvenir")
                else False,
                "stattrak_available": True if
                request.form.get("stattrak")
                else False,
                "stattrak_conditions": {
                    "factory_new": True if
                    request.form.get("fn") and
                    request.form.get("stattrak") else False,
                    "min_wear": True if
                    request.form.get("mw") and
                    request.form.get("stattrak") else False,
                    "field_tested": True if
                    request.form.get("ft") and
                    request.form.get("stattrak") else False,
                    "well_worn": True if
                    request.form.get("ww") and
                    request.form.get("stattrak") else False,
                    "battle_scarred": True if
                    request.form.get("bs") and
                    request.form.get("stattrak") else False
                },
                "conditions": {
                    "factory_new": True if
                    request.form.get("fn")
                    else False,
                    "min_wear": True if
                    request.form.get("mw")
                    else False,
                    "field_tested": True if
                    request.form.get("ft")
                    else False,
                    "well_worn": True if
                    request.form.get("ww")
                    else False,
                    "battle_scarred": True if
                    request.form.get("bs")
                    else False
                },
                "image_urls": {
                    "factory_new": imgDom +
                    request.form.get("fnimage") if
                    request.form.get("fnimage") else None,
                    "min_wear": imgDom +
                    request.form.get("mwimage") if
                    request.form.get("mwimage") else None,
                    "field_tested": imgDom +
                    request.form.get("ftimage") if
                    request.form.get("ftimage") else None,
                    "well_worn": imgDom +
                    request.form.get("ftimage") if
                    request.form.get("wwimage") else None,
                    "battle_scarred": imgDom +
                    request.form.get("bsimage") if
                    request.form.get("bsimage") else None
                },
                "up_votes": 0,
                "down_votes": 0
    }
    if skin_type == "weapon":
        return standard_schema
    if skin_type == "knife":
        keys_to_remove = [
            "weapon_name", "rarity_precedence", "souvenir_available"]
        for key in keys_to_remove:
            standard_schema.pop(key)

        knife_schema = standard_schema
        knife_schema["weapon_type"] = "Knife"
        knife_schema["rarity"] = "Covert"
        return knife_schema
    if skin_type == "gloves":
        keys_to_remove = [
            "weapon_name", "rarity_precedence",
            "souvenir_available", "weapon_type",
            "stattrak_available", "stattrak_conditions"]
        for key in keys_to_remove:
            standard_schema.pop(key)

        gloves_schema = standard_schema
        gloves_schema["rarity"] = "Extraordinary"
        gloves_schema["type"] = "Gloves"
        return gloves_schema

    if skin_type == "case":
        keys_to_remove = [
            "weapon_name", "weapon_type", "rarity",
            "rarity_precedence", "stattrak_available", "souvenir_available",
            "image_urls", "conditions", "stattrak_conditions"]
        for key in keys_to_remove:
            standard_schema.pop(key)

        case_schema = standard_schema
        case_schema["type"] = "Container"
        return case_schema

    if skin_type == "sticker":
        keys_to_remove = [
            "weapon_name", "weapon_type", "rarity_precedence",
            "stattrak_available", "souvenir_available",
            "image_urls", "conditions", "stattrak_conditions"]
        for key in keys_to_remove:
            standard_schema.pop(key)

        sticker_schema = standard_schema
        sticker_schema["type"] = "Sticker"
        sticker_schema["rarity_precedence"] = (
                    6 if request.form.get("rarity") == "Contraband"
                    else 5 if request.form.get("rarity") == "Extraordinary"
                    else 4 if request.form.get("rarity") == "Exotic"
                    else 3 if request.form.get("rarity") == "Remarkable"
                    else 2 if request.form.get("rarity") == "High Grade"
                    else "")

        return sticker_schema


@app.route("/pistols")
def pistols():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "Pistol"}).sort(
        "rarity_precedence", -1).count()
    pistols = skinColl.find({"weapon_type": "Pistol"}).sort(
        "rarity_precedence", -1)

    pistols_paginated = pistols[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/pistols.html", page_title="Pistols",
        pistols=pistols_paginated, pagination=pagination)


@app.route("/rifles")
def rifles():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "Rifle"}).sort(
        "rarity_precedence", -1).count()
    rifles = skinColl.find({"weapon_type": "Rifle"}).sort(
        "rarity_precedence", -1)

    rifles_paginated = rifles[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/rifles.html", page_title="Rifles",
        rifles=rifles_paginated, pagination=pagination)


@app.route("/sniper-rifles")
def sniper_rifles():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "Sniper Rifle"}).sort(
        "rarity_precedence", -1).count()
    snipers = skinColl.find({"weapon_type": "Sniper Rifle"}).sort(
        "rarity_precedence", -1)

    snipers_paginated = snipers[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/sniper-rifles.html", page_title="Sniper Rifles",
        snipers=snipers_paginated, pagination=pagination)


@app.route("/smgs")
def smgs():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "SMG"}).sort(
        "rarity_precedence", -1).count()
    smgs = skinColl.find({"weapon_type": "SMG"}).sort(
        "rarity_precedence", -1)

    smgs_paginated = smgs[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/smgs.html", page_title="SMGs",
        smgs=smgs_paginated, pagination=pagination)


@app.route("/shotguns")
def shotguns():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "Shotgun"}).sort(
        "rarity_precedence", -1).count()
    shotguns = skinColl.find({"weapon_type": "Shotgun"}).sort(
        "rarity_precedence", -1)

    shotguns_paginated = shotguns[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/shotguns.html", page_title="Shotguns",
        shotguns=shotguns_paginated, pagination=pagination)


@app.route("/heavies")
def heavies():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "Machinegun"}).sort(
        "rarity_precedence", -1).count()
    heavies = skinColl.find({"weapon_type": "Machinegun"}).sort(
        "rarity_precedence", -1)

    heavies_paginated = heavies[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/heavies.html", page_title="Heavies",
        heavies=heavies_paginated, pagination=pagination)


@app.route("/knives", methods=["GET", "POST"])
def knives():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"weapon_type": "Knife"}).count()
    knives = skinColl.find({"weapon_type": "Knife"}).sort("release_date", -1)

    knives_paginated = knives[offset: offset + per_page]
    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')
    knifeTypes = skinColl.distinct('knife_type')

    if request.method == "POST":
        print(request.form.get("sortby"))
        total = skinColl.find({
            "weapon_type": "Knife", "knife_type": request.form.get("sortby")
            }).count()
        knives = skinColl.find({
            "weapon_type": "Knife", "knife_type": request.form.get("sortby")
            }).sort("release_date", -1)
        knives_paginated = knives[offset: offset + per_page]
        pagination = Pagination(
            page=page, per_page=per_page,
            total=total, css_framework='bootstrap4')
        return render_template(
            "pages/knives.html", page_title="Knives",
            knives=knives_paginated, pagination=pagination,
            knifeTypes=knifeTypes)

    return render_template(
        "pages/knives.html", page_title="Knives",
        knives=knives_paginated, pagination=pagination,
        knifeTypes=knifeTypes)


@app.route("/gloves")
def gloves():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = skinColl.find({"type": "Gloves"}).sort(
        "rarity_precedence", -1).count()
    gloves = skinColl.find({"type": "Gloves"}).sort(
        "rarity_precedence", -1)

    gloves_paginated = gloves[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/gloves.html", page_title="Gloves",
        gloves=gloves_paginated, pagination=pagination)


@app.route("/cases")
def cases():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = mongo.db.cases.find().sort(
        "rarity_precedence", -1).count()
    cases = mongo.db.cases.find().sort(
        "rarity_precedence", -1)

    cases_paginated = cases[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/cases.html", page_title="Cases",
        cases=cases_paginated, pagination=pagination)


@app.route("/stickers")
def stickers():
    page, per_page, offset = get_page_args(
        page_parameter='page', per_page_parameter='per_page',
        offset_parameter='offset')
    per_page = 20
    offset = (page - 1) * per_page

    total = mongo.db.stickers.find().sort(
        "rarity_precedence", -1).count()
    stickers = mongo.db.stickers.find().sort(
        "rarity_precedence", -1)

    stickers_paginated = stickers[offset: offset + per_page]

    pagination = Pagination(
        page=page, per_page=per_page, total=total, css_framework='bootstrap4')

    return render_template(
        "pages/stickers.html", page_title="Stickers",
        stickers=stickers_paginated, pagination=pagination)


@app.route("/skin/<skinname>", methods=["POST", "GET"])
def skin(skinname):
    if skinColl.find_one({"name": skinname}):
        skin = skinColl.find_one({"name": skinname})
    elif mongo.db.cases.find_one({"name": skinname}):
        skin = mongo.db.cases.find_one({"name": skinname})
    else:
        skin = mongo.db.stickers.find_one({"name": skinname})

    if request.method == "GET":
        if skin:
            return render_template(
                "pages/skin.html", page_title=skin["name"], skin=skin)


@app.route("/api/like-skin", methods=["POST", "GET"])
def like():
    if request.method == "POST":
        reqJson = request.json
        collection = str(reqJson["collection"])

        mongo.db.users.update(
            {"username": session["user"]["username"]},
            {"$push": {"skins_liked": ObjectId(reqJson["_id"])}}
            )

        existing_user = mongo.db.users.find_one(
                 {"username": session["user"]["username"]})

        skins_liked = list(map(str, existing_user["skins_liked"]))
        skins_disliked = list(map(str, existing_user["skins_disliked"]))

        session["user"] = {
                        "username": existing_user["username"],
                        "is_admin": existing_user["is_admin"],
                        "skins_liked": skins_liked,
                        "skins_disliked": skins_disliked}

        skin_upvotes = mongo.db[collection].find_one(
            {"_id": ObjectId(reqJson["_id"])})["up_votes"] + 1

        mongo.db[collection].update(
            {"_id": ObjectId(reqJson["_id"])},
            {"$set": {"up_votes": skin_upvotes}})

        return "liked"
    if request.method == "GET":
        return render_template("error-pages/404.html")


@app.route("/api/dislike-skin", methods=["POST", "GET"])
def dislike():
    if request.method == "POST":
        reqJson = request.json
        collection = str(reqJson["collection"])

        mongo.db.users.update(
            {"username": session["user"]["username"]},
            {"$push": {"skins_disliked": ObjectId(reqJson["_id"])}})

        existing_user = mongo.db.users.find_one(
                 {"username": session["user"]["username"]})

        skins_liked = list(map(str, existing_user["skins_liked"]))
        skins_disliked = list(map(str, existing_user["skins_disliked"]))

        session["user"] = {
                        "username": existing_user["username"],
                        "is_admin": existing_user["is_admin"],
                        "skins_liked": skins_liked,
                        "skins_disliked": skins_disliked}

        skin_downvotes = mongo.db[collection].find_one(
            {"_id": ObjectId(reqJson["_id"])})["down_votes"] + 1

        mongo.db[collection].update(
            {"_id": ObjectId(reqJson["_id"])},
            {"$set": {"down_votes": skin_downvotes}})
        return "disliked"
    if request.method == "GET":
        return render_template("error-pages/404.html")


@app.route("/api/unlike-skin", methods=["POST", "GET"])
def unlike():
    if request.method == "POST":
        reqJson = request.json

        skin_id = ObjectId(reqJson["_id"])
        collection = str(reqJson["collection"])

        mongo.db.users.update(
            {"username": session["user"]["username"]},
            {"$pull": {"skins_liked": skin_id}})

        existing_user = mongo.db.users.find_one(
                 {"username": session["user"]["username"]})

        skins_liked = list(map(str, existing_user["skins_liked"]))
        skins_disliked = list(map(str, existing_user["skins_disliked"]))

        session["user"] = {
                        "username": existing_user["username"],
                        "is_admin": existing_user["is_admin"],
                        "skins_liked": skins_liked,
                        "skins_disliked": skins_disliked}

        skin_upvotes = mongo.db[collection].find_one({
            "_id": skin_id
        })["up_votes"]

        mongo.db[collection].update(
            {"_id": skin_id}, {"$set": {"up_votes": skin_upvotes - 1}})

    return "Unliked"


@app.route("/api/undislike-skin", methods=["POST", "GET"])
def undislike():
    if request.method == "POST":
        reqJson = request.json

        skin_id = ObjectId(reqJson["_id"])
        collection = str(reqJson["collection"])

        mongo.db.users.update(
            {"username": session["user"]["username"]},
            {"$pull": {"skins_disliked": skin_id}})

        existing_user = mongo.db.users.find_one(
                 {"username": session["user"]["username"]})

        skins_liked = list(map(str, existing_user["skins_liked"]))
        skins_disliked = list(map(str, existing_user["skins_disliked"]))

        session["user"] = {
                        "username": existing_user["username"],
                        "is_admin": existing_user["is_admin"],
                        "skins_liked": skins_liked,
                        "skins_disliked": skins_disliked}

        skin_downvotes = mongo.db[collection].find_one({
            "_id": skin_id
        })["down_votes"]

        mongo.db[collection].update(
            {"_id": skin_id}, {"$set": {"down_votes": skin_downvotes - 1}})

        return "undisliked"


if __name__ == '__main__':
    app.run(
        host=os.environ.get("IP"),
        port=int(os.environ.get("PORT"))
    )
