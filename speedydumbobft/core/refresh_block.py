def refresh_block(pid, N, f, propose, add_put_in, refresh_get_out, logger=None):
    add_put_in(propose)

    value_all = refresh_get_out()
    return value_all