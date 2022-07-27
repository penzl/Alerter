from Website_helpers import *

app = Flask(__name__)
app.config["DEBUG"] = True


@app.route('/', methods=['GET', 'POST'])
def test():
    if request.method == 'POST':
        for i, j in enumerate(values):
            if request.form.get(j) == j:
                result = request.form[j]
                pass
        daily, weekly, trends, strategies, tickers, alerts, vol_prof = create_all_data(result)
        return render_template('website.html', dta=daily | weekly | strategies | alerts | {"trends": trends} | vol_prof,
                               tickers=tickers, result="TSLA")
    else:
        daily, weekly, trends, strategies, tickers, alerts, vol_prof = create_all_data("BTC-USD")
        # with open('json_data.json', 'w') as outfile:
        #    json.dump(json.dumps(daily | weekly | strategies | alerts | {"trends": trends} | vol_prof), outfile)
        return render_template('website.html',
                               dta=daily | weekly | strategies | alerts | {"trends": trends} | vol_prof,
                               tickers=tickers, result="TSLA")


if __name__ == "__main__":
    app.run(port=5111, debug=True)
