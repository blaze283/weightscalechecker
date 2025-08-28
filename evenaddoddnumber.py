
import streamlit as s
import mysql.connector

def connect_db():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='root',
        database='mybank'
    )

def create_account(cursor, mydb, cname, amount, pin, password):
    query = "INSERT INTO customer_ac (cname, balance, pin, password) VALUES (%s, %s, %s, %s)"
    val = [cname, amount, pin, password]
    cursor.execute(query, val)
    mydb.commit()
    s.success('Account created successfully')

def authenticate_user(cursor, ac_no, password):
    query = f"SELECT password, cname FROM customer_ac WHERE ac_no={ac_no}"
    cursor.execute(query)
    fetch = cursor.fetchall()
    if fetch:
        password_db = fetch[0][0]
        cname = fetch[0][1]
        return password == password_db, cname
    return False, None

def deposit_amount(cursor, mydb, ac_no, pin, amt):
    query = f"SELECT pin FROM customer_ac WHERE ac_no={ac_no}"
    cursor.execute(query)
    d = cursor.fetchall()
    if d and pin == d[0][0]:
        query = f"UPDATE customer_ac SET balance = balance + {amt} WHERE ac_no = {ac_no}"
        cursor.execute(query)
        mydb.commit()
        s.success('Amount Deposited Successfully')
    else:
        s.error('Invalid PIN !!!')

def withdraw_amount(cursor, mydb, ac_no, pin, amt):
    query = f"SELECT pin, balance FROM customer_ac WHERE ac_no={ac_no}"
    cursor.execute(query)
    d = cursor.fetchall()
    if d and pin == d[0][0]:
        if d[0][1] > 0 and amt <= d[0][1]:
            query = f"UPDATE customer_ac SET balance = balance - {amt} WHERE ac_no = {ac_no}"
            cursor.execute(query)
            mydb.commit()
            s.success(f'{amt} has been debited from your account')
        elif d[0][1] == 0:
            s.error('ACCOUNT CONTAINS: 0rs')
        else:
            s.error('INSUFFICIENT BALANCE')
    else:
        s.error('Invalid PIN !!!')

def check_balance(cursor, ac_no, pin):
    query = f"SELECT pin, balance FROM customer_ac WHERE ac_no={ac_no}"
    cursor.execute(query)
    d = cursor.fetchall()
    if d and pin == d[0][0]:
        s.success(f'Account Balance is: {d[0][1]} RS')
    else:
        s.error('Invalid PIN !!!')

def main():
    mydb = connect_db()
    cursor = mydb.cursor()

    s.sidebar.header('WELCOME TO THE BANK')

    ac_no = s.sidebar.number_input('ACCOUNT NUMBER', min_value=0)
    password = s.sidebar.text_input('PASSWORD', type='password')
    login = s.sidebar.button('LOGIN', type='primary')
    signup = s.sidebar.button('SIGN-UP')

    if 'signin' not in s.session_state:
        s.session_state.signin = False

    if signup:
        s.session_state.signin = True

    if s.session_state.signin:
        cname = s.text_input('NAME')
        amount = s.number_input('AMOUNT', min_value=1000)
        pin = s.number_input('CREATE A PIN', min_value=0)
        password = s.text_input('CREATE A PASSWORD', type="password")
        submit = s.button('Create the account', type='primary')
        if submit:
            create_account(cursor, mydb, cname, amount, pin, password)

    if 'logged' not in s.session_state:
        s.session_state.logged = False

    if login:
        is_authenticated, cname = authenticate_user(cursor, ac_no, password)
        if is_authenticated:
            s.sidebar.success('Login successful...')
            s.session_state.logged = True
            s.subheader(f'Welcome {cname}')
        else:
            s.sidebar.error('Incorrect Password or Account Number!!!')

    if s.session_state.logged:
        radio = s.radio('Choose the Option:', ['Deposit', 'Withdraw', 'Balance'])

        if radio == 'Deposit':
            pin = s.number_input("Enter the PIN", min_value=0)
            amt = s.number_input("Enter the Amount to deposit", min_value=0)
            if s.button('Deposit'):
                deposit_amount(cursor, mydb, ac_no, pin, amt)

        elif radio == 'Withdraw':
            pin = s.number_input('Enter the PIN', min_value=0)
            amt = s.number_input('Enter the Amount:', min_value=0)
            if s.button('Withdraw'):
                withdraw_amount(cursor, mydb, ac_no, pin, amt)

        elif radio == 'Balance':
            pin = s.number_input('Enter the PIN', min_value=0)
            if s.button('Check Balance'):
                check_balance(cursor, ac_no, pin)

if __name__ == '__main__':
    main()










