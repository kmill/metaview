
def nice_date_format(date) :
    if date.hour == date.minute == date.second == 0 :
        return date.strftime("%a, %b %e %Y")
    elif date.minute == date.second == 0 :
        return date.strftime("%a, %b %e %Y, %l %p")
    elif date.second == 0 :
        return date.strftime("%a, %b %e %Y, %l:%M %p")
    else :
        return date.strftime("%a, %b %e %Y, %l:%M:%S %p")
