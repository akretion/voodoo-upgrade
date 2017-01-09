# -*- python -*-
# coding: utf-8

from psycopg2.extensions import AsIs


def run(session, logger):
    # TODO check if needed
    fk_on_query = """
        SELECT cl1.relname as table,
                att1.attname as column
           FROM pg_constraint as con, pg_class as cl1, pg_class as cl2,
                pg_attribute as att1, pg_attribute as att2
          WHERE con.conrelid = cl1.oid
            AND con.confrelid = cl2.oid
            AND array_lower(con.conkey, 1) = 1
            AND con.conkey[1] = att1.attnum
            AND att1.attrelid = cl1.oid
            AND cl2.relname = %s
            AND att2.attname = 'id'
            AND array_lower(con.confkey, 1) = 1
            AND con.confkey[1] = att2.attnum
            AND att2.attrelid = cl2.oid
            AND con.contype = 'f'
    """
    logger.info("Deduplicate currency by name: Update all foreign key related"
                " to res_currency to first id of those duplicated")
    session.cr.execute(fk_on_query, ('res_currency',))

    for table, column in session.cr.fetchall():
        query_dic = {
                'table': AsIs(table),
                'column': AsIs(column),
        }
        query = """
            UPDATE "%(table)s" as to_update
            SET %(column)s = dups.first_id
            FROM (
            select * from  (
              SELECT id, first_value(id) OVER (
                PARTITION BY name ORDER BY id
              ) first_id
              FROM res_currency
              WHERE name IN (
                SELECT name
                FROM res_currency
                GROUP BY name
                HAVING count(name) > 1
              )
            ) d) as dups
            WHERE to_update.%(column)s != dups.first_id
            and to_update.%(column)s = dups.id;
            """
        session.cr.execute(query, query_dic)

    logger.info("Delete duplicated currency ")
    delete_duplicate_val = """
    DELETE FROM res_currency
        USING (
          SELECT id, first_value(id) OVER (
            PARTITION BY name ORDER BY id
          ) first_id
          FROM res_currency
          WHERE name IN (
            SELECT name
            FROM res_currency
            GROUP BY name
            HAVING count(name) > 1
          )
        ) dups
        WHERE dups.id != dups.first_id
        AND res_currency.id = dups.id;
    """

    session.cr.execute(delete_duplicate_val)
    # TODO seem to be not needed anymore
    # session.cr.execute("UPDATE res_currency set company_id = null")
    try:
        session.cr.execute(
            "ALTER TABLE product_product ADD column product_image bytea")
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception("ALTER TABLE product_product ERROR: %s", e.message)

    # Clean Data base before migration
    try:
        # Delete partner id referenced but not present in res_partner
        # (wrong FK)
        session.cr.execute("""
            UPDATE account_move set partner_id = NULL
            where id in (SELECT m.id FROM  account_move m
                where partner_id is not null EXCEPT select m.id from
                account_move m INNER join res_partner p on p.id = m.partner_id
                );
            UPDATE stock_picking set partner_id = NULL where partner_id in (
                SELECT partner_id from stock_picking
                    WHERE partner_id IS NOT NULL
                        EXCEPT SELECT id from res_partner);
            UPDATE purchase_order_line SET partner_id = NULL
                where partner_id IN (
                    SELECT partner_id FROM Purchase_order_line
                        WHERE partner_id IS NOT NULL
                            EXCEPT SELECT id from res_partner);
            UPDATE stock_move SET partner_id = NULL where partner_id IN (
                SELECT partner_id FROM stock_move
                    WHERE partner_id IS NOT NULL
                        EXCEPT SELECT id from res_partner);
            UPDATE account_invoice_line SET partner_id = NULL
                where partner_id IN (
                    SELECT partner_id FROM account_invoice_line
                        WHERE partner_id IS NOT NULL
                            EXCEPT SELECT id from res_partner);
            UPDATE external_referential SET last_imported_partner_id = NULL
                where last_imported_partner_id IN (
                    SELECT last_imported_partner_id FROM external_referential
                        WHERE last_imported_partner_id IS NOT NULL
                            EXCEPT SELECT id from res_partner);
            """)
        # Delete user id referenced but not present in res_users (wrong FK)
        session.cr.execute("""
            UPDATE sale_order_line SET salesman_id = NULL
                where salesman_id IN (
                    SELECT salesman_id FROM sale_order_line
                        WHERE salesman_id IS NOT NULL
                            EXCEPT SELECT id from res_users);
            """)
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception("Clean Data error : %s", e.message)

    try:
        # Fix bug update modules ?
        session.cr.execute("""
            ALTER TABLE res_groups ADD COLUMN is_portal boolean;
            """)
        session.cr.execute("""
            ALTER TABLE res_groups ADD COLUMN share boolean;
            """)
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception("ALTER TABLE res_groups ERROR: %s", e.message)

    try:
        # Fix bug update modules ?
        session.cr.execute("""
            ALTER TABLE res_users ADD COLUMN share boolean;
            """)
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception("ALTER TABLE res_users ERROR: %s", e.message)

    try:
        # Fix bug update modules ?
        session.cr.execute("""
            ALTER TABLE res_partner ADD COLUMN signup_type varchar(32);
            ALTER TABLE res_partner ADD COLUMN signup_expiration timestamp;
            ALTER TABLE res_partner ADD COLUMN signup_token varchar(32);
            ALTER TABLE res_partner ADD COLUMN display_name varchar(64);
            """)
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception("ALTER TABLE res_partner ERROR: %s", e.message)

    try:
        # Save VAT IN Other COLUMN and set VAT to null
        # to skip vat validation error
        session.cr.execute(
            "ALTER TABLE res_partner "
            "ADD COLUMN openupgrade_7_save_vat VARCHAR(32)")
        session.cr.execute(
            "UPDATE res_partner set VAT = NULL WHERE VAT = ''; "
            "UPDATE res_partner set openupgrade_7_save_vat = VAT "
            "WHERE VAT IS NOT NULL;"
            "UPDATE res_partner set  VAT = NULL WHERE VAT IS NOT NULL;")
        session.cr.execute("""
            delete from  ir_sequence_type where code = 'stock.picking';""")
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception(
            "res_partner "
            "openupgrade_7_save_vat update ERROR : %s", e.message)

    session.cr.execute("""UPDATE sale_order_line
        SET order_partner_id = sale_order.partner_id
        FROM sale_order
        WHERE sale_order.id = sale_order_line.order_id
        AND sale_order.partner_id != sale_order_line.order_partner_id""")

    # DELETE the decimal precision Product Price that can be added by oca module
    # and conflict with the new odoo version
    session.cr.execute("DELETE FROM decimal_precision WHERE name ='Product Price'")

    logger.info("Begin of odoo modules update")
    session.cr.commit()
    session.update_modules(['all'])

    try:
        # Save VAT IN Other COLUMN and set VAT to null
        # to skip vat validation error
        session.cr.execute(
            "UPDATE res_partner set VAT = openupgrade_7_save_vat "
            "WHERE openupgrade_7_save_vat IS NOT NULL;"
        )
        session.cr.execute(
            "ALTER TABLE res_partner "
            "ADD DROP openupgrade_7_save_vat")
        session.cr.commit()
    except Exception as e:
        session.cr.rollback()
        logger.exception(
            "res_partner "
            "vat update ERROR : %s", e.message)
