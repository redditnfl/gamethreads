GS_UNKNOWN = 'UNKNOWN'
GS_PENDING = 'Not started'
GS_Q1 = 'Q1'
GS_Q2 = 'Q2'
GS_HT = 'Halftime'
GS_Q3 = 'Q3'
GS_Q4 = 'Q4'
GS_F  = 'Final'
GS_OT = 'OT'
GS_FO = 'Final (OT)'

GS = [GS_UNKNOWN, GS_PENDING, GS_Q1, GS_Q2, GS_HT, GS_Q3, GS_Q4, GS_OT, GS_F, GS_FO]
GS_PLAYING = [GS_Q1, GS_Q2, GS_HT, GS_Q3, GS_Q4, GS_OT]
GS_FINAL = [GS_F, GS_FO]
GS_OT_STATES = [GS_OT, GS_FO]

EV_KICKOFF_SCHEDULED = 'Kickoff (scheduled)'
EV_KICKOFF_ACTUAL = 'Kickoff (actual)'
EV_Q2_START = 'Q2 Start'
EV_HALFTIME_START = 'Halftime start'
EV_Q3_START = 'Q3 Start'
EV_Q4_START = 'Q4 Start'
EV_FINAL = 'Final'
EV_OT_START = 'OT Start'
EV_FINAL_OT = 'Final (OT)'

EV_Q1_END = EV_Q2_START
EV_Q2_END = EV_HALFTIME_START
EV_HALFTIME_END = EV_Q3_START
EV_Q3_END = EV_Q4_START
EV_Q1_START = EV_KICKOFF_ACTUAL

EVENTS = set([EV_KICKOFF_SCHEDULED, EV_KICKOFF_ACTUAL, EV_Q1_START, EV_Q1_END, EV_Q2_START, EV_Q2_END, EV_HALFTIME_START, EV_Q3_START, EV_Q3_END, EV_Q4_START, EV_FINAL, EV_OT_START, EV_FINAL_OT])

GS_TRANSITIONS = {
        (None, GS_PENDING): EV_KICKOFF_SCHEDULED,
        (GS_PENDING, GS_Q1): EV_KICKOFF_ACTUAL,
        (GS_Q1, GS_Q2): EV_Q2_START,
        (GS_Q2, GS_HT): EV_HALFTIME_START,
        (GS_HT, GS_Q3): EV_Q3_START,
        (GS_Q3, GS_Q4): EV_Q4_START,
        }
GS_TRANSITIONS_NORMAL = {
        (GS_Q4, GS_F): EV_FINAL,
        }
GS_TRANSITIONS_OT = {
        (GS_Q4, GS_OT): EV_OT_START,
        (GS_OT, GS_FO): EV_FINAL_OT,
        }

PRE = 'PRE'
REG = 'REG'
POST = 'POST'

GAME_TYPES = [PRE, REG, POST]
