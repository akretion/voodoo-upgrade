# -*- python -*-
# coding: utf-8

def run(session, logger):
    # TODO FIXME
    session.cr.execute("""DELETE FROM account_bank_statement""")
    #WHERE profile_id in (
    #    SELECT id from account_statement_profile where one_move=True)""")
    session.cr.commit()
    session.update_modules(['all'])
