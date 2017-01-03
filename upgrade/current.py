# -*- python -*-
# coding: utf-8

def run(session, logger):
    # Add you custom pre migration here
    session.update_modules(['all'])
    # Add your post migration here
