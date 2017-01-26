from flask import Flask, render_template
from flask_ask import Ask, question, session, statement

from helper import __get_narrative, __build_url, __email_narrative, __good_state_check


app = Flask(__name__)
ask = Ask(app, '/')


@ask.launch
def new_ask():
    welcome = render_template('welcome')
    reprompt = render_template('reprompt')
    return question(welcome).reprompt(reprompt)


@ask.intent('GetState')
def get_state(state):
    print('selected state: ', state)
    if not __good_state_check(state):
        return question(render_template('reprompt'))

    session.attributes = {'state': state,
                          'url': __build_url(state),
                          'narrative': __get_narrative(state)}

    if session.attributes.get('email'):
        return __email_narrative(session_attributes.copy())

    clean_narrative = session.attributes['narrative'].replace('\n', '')\
                                                     .replace('&', 'and')
    return question(clean_narrative + " " + render_template('followup')).\
           reprompt(render_template('reprompt_email'))


@ask.intent('YesIntent')
def yes_intent(state):
    print('yes intent state: ', state)
    if not __good_state_check(state):
        return question(render_template('reprompt'))

    if session.attributes.get('state'):
        session.attributes['state'] = state
        return __email_narrative(session.attributes)
    else:
        session.attributes['email'] = True
        return question(render_template('nostate'))


@ask.intent('AMAZON.YesIntent')
def yes_intent():
    if session.attributes.get('state'):
        return __email_narrative(session.attributes)
    else:
        session.attributes = {}
        return question(render_template('reprompt_state'))


@ask.intent('AMAZON.NoIntent')
def no_intent():
    if not session.attributes.get('state'):
        return question(render_template('reprompt_state'))
    session.attributes = {}
    return question(render_template('confirmation2'))


@ask.intent('AMAZON.StopIntent')
def no_intent():
    return statement(render_template('goodbye'))


if __name__ == '__main__':
    app.run()
