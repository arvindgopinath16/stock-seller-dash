import dash
from dash import dcc, html, Input, Output, callback_context
import plotly.graph_objs as go
import plotly.express as px
from datetime import datetime, timedelta
import yfinance as yf
import ta
import pandas as pd
import numpy as np
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import os

# Initialize the Dash app with Bootstrap theme
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title = "Stock Sell Signal Analyzer"

# Define the layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("📈 Stock Sell Signal Analyzer", className="text-center mb-4"),
            html.P("Analyze stocks for profit-taking opportunities using Bollinger Bands, RSI, and MACD", 
                   className="text-center text-muted")
        ])
    ]),
    
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5("🎯 Analysis Parameters", className="card-title"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("Stock Symbols (comma-separated):"),
                            dcc.Input(
                                id='stock-input',
                                type='text',
                                value='AAPL,MSFT,GOOGL,AMZN,TSLA',
                                placeholder='Enter stock symbols...',
                                className='form-control'
                            )
                        ], width=6),
                        dbc.Col([
                            html.Label("Analysis Period:"),
                            dcc.Dropdown(
                                id='period-dropdown',
                                options=[
                                    {'label': '1 Month', 'value': '1mo'},
                                    {'label': '3 Months', 'value': '3mo'},
                                    {'label': '6 Months', 'value': '6mo'},
                                    {'label': '1 Year', 'value': '1y'}
                                ],
                                value='6mo',
                                className='form-control'
                            )
                        ], width=6)
                    ], className='mb-3'),
                    dbc.Button("🚀 Analyze Stocks", id='analyze-btn', 
                              color="primary", size="lg", className='w-100')
                ])
            ], className='mb-4')
        ])
    ]),
    
    # Loading spinner
    dcc.Loading(
        id="loading-1",
        type="default",
        children=[
            # Results section
            html.Div(id='results-container', style={'display': 'none'})
        ]
    ),
    
    # Hidden div to store data
    dcc.Store(id='stocks-data-store'),
    
    # Footer
    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P("Built with Dash • Data from Yahoo Finance • Technical indicators from TA-Lib", 
                   className="text-center text-muted")
        ])
    ])
], fluid=True)

# Function to analyze stocks (similar to your original script)
def analyze_stocks(stock_symbols, period):
    stocks_data = {}
    stock_symbols = [s.strip().upper() for s in stock_symbols.split(',') if s.strip()]
    
    for stock in stock_symbols:
        try:
            # Fetch historical data
            data = yf.download(stock, period=period, interval="1h")
            
            if data.empty:
                stocks_data[stock] = {
                    'status': 'error',
                    'message': 'No data available',
                    'conditions': [False, False, False],
                    'indicators': {}
                }
                continue
            
            # Handle column names
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(1)
            
            # Ensure we have the right columns
            expected_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if len(data.columns) >= 5:
                data = data.iloc[:, :5]
                data.columns = expected_cols
            
            # Resample to 4-hour intervals
            agg_dict = {
                'Open': 'first',
                'High': 'max', 
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }
            
            data_4h = data.resample('4H').agg(agg_dict).dropna()
            
            if len(data_4h) < 100:
                stocks_data[stock] = {
                    'status': 'error',
                    'message': f'Insufficient data: {len(data_4h)} points (need 100+)',
                    'conditions': [False, False, False],
                    'indicators': {}
                }
                continue
            
            # Calculate indicators
            close_col = 'Close'
            
            # Bollinger Bands
            bb_indicator = ta.volatility.BollingerBands(
                close=data_4h[close_col], window=100, window_dev=2
            )
            bb_high = bb_indicator.bollinger_hband()
            bb_low = bb_indicator.bollinger_lband()
            
            # RSI
            rsi = ta.momentum.RSIIndicator(data_4h[close_col], window=10).rsi()
            
            # MACD
            macd_indicator = ta.trend.MACD(
                data_4h[close_col], window_slow=21, window_fast=8, window_sign=5
            )
            macd = macd_indicator.macd()
            macd_signal = macd_indicator.macd_signal()
            
            # Check conditions
            latest_close = data_4h[close_col].iloc[-1]
            latest_bb_high = bb_high.iloc[-1]
            latest_rsi = rsi.iloc[-1]
            latest_macd = macd.iloc[-1]
            latest_macd_signal = macd_signal.iloc[-1]
            
            conditions = [
                latest_close > latest_bb_high if pd.notna(latest_bb_high) else False,
                latest_rsi > 70 if pd.notna(latest_rsi) else False,
                latest_macd < latest_macd_signal if pd.notna(latest_macd) and pd.notna(latest_macd_signal) else False
            ]
            
            stocks_data[stock] = {
                'status': 'success',
                'data': data_4h,
                'conditions': conditions,
                'indicators': {
                    'close': latest_close,
                    'bb_high': latest_bb_high,
                    'bb_low': bb_low.iloc[-1] if pd.notna(bb_low.iloc[-1]) else None,
                    'rsi': latest_rsi,
                    'macd': latest_macd,
                    'macd_signal': latest_macd_signal
                }
            }
            
        except Exception as e:
            stocks_data[stock] = {
                'status': 'error',
                'message': str(e),
                'conditions': [False, False, False],
                'indicators': {}
            }
    
    return stocks_data

# Callback to analyze stocks
@app.callback(
    [Output('stocks-data-store', 'data'),
     Output('results-container', 'children'),
     Output('results-container', 'style')],
    [Input('analyze-btn', 'n_clicks')],
    [Input('stock-input', 'value'),
     Input('period-dropdown', 'value')],
    prevent_initial_call=True
)
def update_analysis(n_clicks, stock_symbols, period):
    if not n_clicks:
        raise PreventUpdate
    
    # Analyze stocks
    stocks_data = analyze_stocks(stock_symbols, period)
    
    # Create results display
    results = []
    
    # Summary statistics
    successful = sum(1 for data in stocks_data.values() if data['status'] == 'success')
    errors = len(stocks_data) - successful
    
    if successful > 0:
        sell_signals_2 = sum(1 for data in stocks_data.values() 
                            if data['status'] == 'success' and sum(data['conditions']) == 2)
        sell_signals_3 = sum(1 for data in stocks_data.values() 
                            if data['status'] == 'success' and sum(data['conditions']) == 3)
        no_sell_signals = sum(1 for data in stocks_data.values() 
                             if data['status'] == 'success' and sum(data['conditions']) <= 1)
        
        summary_card = dbc.Card([
            dbc.CardBody([
                html.H4("📊 Analysis Summary", className="card-title"),
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3(f"{sell_signals_3}", className="text-success"),
                                html.P("Strong Sell (3 conditions)", className="mb-0")
                            ])
                        ], color="success", outline=True)
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3(f"{sell_signals_2}", className="text-warning"),
                                html.P("Moderate Sell (2 conditions)", className="mb-0")
                            ])
                        ], color="warning", outline=True)
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3(f"{no_sell_signals}", className="text-danger"),
                                html.P("No Sell Signal (0-1 conditions)", className="mb-0")
                            ])
                        ], color="danger", outline=True)
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H3(f"{errors}", className="text-secondary"),
                                html.P("Data Errors", className="mb-0")
                            ])
                        ], color="secondary", outline=True)
                    ], width=3)
                ])
            ])
        ], className="mb-4")
        results.append(summary_card)
    
    # Stock details table
    table_rows = []
    for stock, data in stocks_data.items():
        if data['status'] == 'success':
            conditions = data['conditions']
            true_count = sum(conditions)
            
            # Determine row color based on conditions
            if true_count == 3:
                row_color = "table-success"
            elif true_count == 2:
                row_color = "table-warning"
            else:
                row_color = "table-danger"
            
            table_rows.append(html.Tr([
                html.Td(stock, className="fw-bold"),
                html.Td("✅" if conditions[0] else "❌"),
                html.Td("✅" if conditions[1] else "❌"),
                html.Td("✅" if conditions[2] else "❌"),
                html.Td(f"{true_count}/3", className="fw-bold"),
                html.Td(f"${data['indicators']['close']:.2f}" if data['indicators']['close'] else "N/A"),
                html.Td(f"{data['indicators']['rsi']:.1f}" if data['indicators']['rsi'] else "N/A")
            ], className=row_color))
        else:
            table_rows.append(html.Tr([
                html.Td(stock, className="fw-bold"),
                html.Td("❌", colSpan=6, className="text-center text-muted"),
                html.Td(data['message'], className="text-muted")
            ], className="table-secondary"))
    
    table = dbc.Card([
        dbc.CardBody([
            html.H4("📋 Stock Analysis Results", className="card-title"),
            dbc.Table([
                html.Thead([
                    html.Tr([
                        html.Th("Stock"),
                        html.Th("Above BB High"),
                        html.Th("RSI > 70"),
                        html.Th("MACD < Signal"),
                        html.Th("Sell Score"),
                        html.Th("Current Price"),
                        html.Th("RSI Value")
                    ])
                ]),
                html.Tbody(table_rows)
            ], bordered=True, hover=True, responsive=True)
        ])
    ])
    results.append(table)
    
    # Charts for successful stocks
    successful_stocks = {k: v for k, v in stocks_data.items() if v['status'] == 'success'}
    if successful_stocks:
        charts_card = dbc.Card([
            dbc.CardBody([
                html.H4("📈 Technical Analysis Charts", className="card-title"),
                dcc.Dropdown(
                    id='chart-stock-dropdown',
                    options=[{'label': stock, 'value': stock} for stock in successful_stocks.keys()],
                    value=list(successful_stocks.keys())[0] if successful_stocks else None,
                    className='mb-3'
                ),
                dcc.Graph(id='stock-chart')
            ])
        ])
        results.append(charts_card)
    
    return stocks_data, results, {'display': 'block'}

# Callback to update stock chart
@app.callback(
    Output('stock-chart', 'figure'),
    [Input('chart-stock-dropdown', 'value')],
    [Input('stocks-data-store', 'data')]
)
def update_stock_chart(selected_stock, stocks_data):
    if not selected_stock or not stocks_data or selected_stock not in stocks_data:
        return go.Figure()
    
    stock_data = stocks_data[selected_stock]
    if stock_data['status'] != 'success':
        return go.Figure()
    
    data = stock_data['data']
    indicators = stock_data['indicators']
    
    # Create candlestick chart
    fig = go.Figure()
    
    # Candlesticks
    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data['Open'],
        high=data['High'],
        low=data['Low'],
        close=data['Close'],
        name='Price',
        increasing_line_color='#26A69A',
        decreasing_line_color='#EF5350'
    ))
    
    # Bollinger Bands
    if indicators['bb_high'] is not None:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['BB_High'] if 'BB_High' in data.columns else [indicators['bb_high']] * len(data),
            mode='lines',
            name='BB Upper',
            line=dict(color='rgba(255, 193, 7, 0.5)', dash='dash')
        ))
    
    if indicators['bb_low'] is not None:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data['BB_Low'] if 'BB_Low' in data.columns else [indicators['bb_low']] * len(data),
            mode='lines',
            name='BB Lower',
            line=dict(color='rgba(255, 193, 7, 0.5)', dash='dash')
        ))
    
    fig.update_layout(
        title=f'{selected_stock} - Technical Analysis',
        xaxis_title='Date',
        yaxis_title='Price ($)',
        height=500,
        showlegend=True
    )
    
    return fig

# For production deployment
server = app.server

# Run the app (only for local development)
if __name__ == '__main__':
    # For production, use environment variable for port
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=False, host='0.0.0.0', port=port)
