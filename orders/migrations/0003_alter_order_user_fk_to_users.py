# Switch Order.user FK from auth.User to users.User (AUTH_USER_MODEL)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_add_initial_delivery_methods"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE orders_order "
                "DROP CONSTRAINT IF EXISTS orders_order_user_id_e9b59eb1_fk_auth_user_id;"
            ),
            reverse_sql=(
                "ALTER TABLE orders_order "
                "ADD CONSTRAINT orders_order_user_id_e9b59eb1_fk_auth_user_id "
                "FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;"
            ),
        ),
        migrations.RunSQL(
            sql=(
                "ALTER TABLE orders_order "
                "ADD CONSTRAINT orders_order_user_id_fk_users_user "
                "FOREIGN KEY (user_id) REFERENCES users_user(id) DEFERRABLE INITIALLY DEFERRED;"
            ),
            reverse_sql=(
                "ALTER TABLE orders_order "
                "DROP CONSTRAINT IF EXISTS orders_order_user_id_fk_users_user;"
            ),
        ),
    ]
