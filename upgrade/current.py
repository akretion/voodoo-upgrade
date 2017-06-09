# -*- python -*-
# coding: utf-8

def run(session, logger):
    session.cr.execute("""DELETE FROM account_bank_statement WHERE id in (
        SELECT statement_id
        FROM account_bank_statement_line
        WHERE statement_id IN (
          SELECT statement_id
          FROM account_move_line
          GROUP BY statement_id
          HAVING count(distinct(move_id)) = 1)
        GROUP BY statement_id
        HAVING count(id) > 1
        )""")
    session.cr.commit()
    session.update_modules(['all'])


