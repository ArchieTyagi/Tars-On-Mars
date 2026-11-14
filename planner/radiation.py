"""Radiation picked up during an outing.

We do not model radiation. We use the dose rate that instruments measured on the surface and
multiply by the hours outside. That is the steady background from cosmic rays. A solar storm
can add a lot more on top, and no map can predict one.

Mars: Curiosity's RAD instrument at Gale crater, first ~300 sols, 0.64 mSv per day
      (Hassler et al. 2014, Science 343, doi:10.1126/science.1244797).
Moon: Chang'E-4 lander's LND instrument, Von Karman crater, 1369 microsieverts per day
      (Zhang et al. 2020, Science Advances 6, doi:10.1126/sciadv.aaz1334).
"""

MEASURED = {
    "mars": {
        "usv_per_day": 640.0,
        "measured_at": "Gale crater, by Curiosity's RAD instrument (2012-2013)",
        "source": "Hassler et al. 2014, Science 343, doi:10.1126/science.1244797",
        "note": "Measured at Gale crater, not at this site: no radiation instrument has flown to Jezero. "
                "It is the steady cosmic-ray background and it changes with the solar cycle. "
                "Solar storms are not included and can add much more. Suit shielding is not modelled.",
    },
    "moon": {
        "usv_per_day": 1369.0,
        "measured_at": "Von Karman crater on the far side, by the Chang'E-4 lander's LND instrument (2019)",
        "source": "Zhang et al. 2020, Science Advances 6, eaaz1334, doi:10.1126/sciadv.aaz1334",
        "note": "Measured at the Chang'E-4 landing site, not at this site. "
                "It is the steady cosmic-ray background and it changes with the solar cycle. "
                "Solar storms are not included and can add much more. Suit shielding is not modelled.",
    },
}


def outing(body, hours):
    """Dose for `hours` outside (Earth hours), in microsieverts. None if nobody has measured that body."""
    m = MEASURED.get(body)
    if m is None:
        return None
    rate = m["usv_per_day"] / 24.0
    return {"dose_usv": round(rate * float(hours), 1), "rate_usv_per_h": round(rate, 2),
            "measured_at": m["measured_at"], "source": m["source"], "note": m["note"]}
