import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
from textblob import TextBlob
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sqlite3
from flask import Flask, render_template, jsonify
import schedule
import time
import threading
import re

# Configuração inicial
app = Flask(__name__)


# Classe para coleta de notícias
class NewsScraper:

    def __init__(self):
        self.sources = [{
            'name': 'G1 Economia',
            'url': 'https://g1.globo.com/economia/',
            'selectors': {
                'articles': '.feed-post',
                'title': '.feed-post-link',
                'summary': '.feed-post-body-resumo'
            }
        }]

    def scrape_news(self):
        all_news = []

        for source in self.sources:
            try:
                response = requests.get(source['url'], timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                articles = soup.select(source['selectors']['articles'])

                for article in articles[:5]:
                    # Limita a 5 artigos por fonte
                    title_elem = article.select_one(
                        source['selectors']['title'])
                    summary_elem = article.select_one(
                        source['selectors']['summary'])

                    if title_elem:
                        title = title_elem.get_text().strip()
                        link = title_elem['href'] if title_elem.has_attr(
                            'href') else ''

                        summary = summary_elem.get_text().strip(
                        ) if summary_elem else ''

                        # Análise de sentimento simples
                        sentiment = self.analyze_sentiment(title + " " +
                                                           summary)

                        all_news.append({
                            'title':
                            title,
                            'summary':
                            summary,
                            'link':
                            link,
                            'source':
                            source['name'],
                            'sentiment':
                            sentiment,
                            'date':
                            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
            except Exception as e:
                print(
                    f"Erro ao coletar notícias de {source['name']}: {str(e)}")

        return all_news

    def analyze_sentiment(self, text):
        # Limpeza do texto
        text = re.sub(r'[^\w\s]', '', text)
        text_lower = text.lower()

        # Palavras-chave específicas para economia brasileira
        positive_words = [
            # Economia geral
            'crescimento',
            'alta',
            'subiu',
            'aumento',
            'lucro',
            'ganho',
            'melhora',
            'recuperação',
            'expansão',
            'otimista',
            'positivo',
            'benefício',
            'prosperidade',
            'sucesso',
            'oportunidade',
            # Mercado financeiro
            'valorização',
            'rendimento',
            'investimento',
            'dividendos',
            'superávit',
            'receita',
            # Política econômica
            'acordo',
            'negociação',
            'cooperação',
            'parceria',
            'aliança',
            'estabilidade',
            # Indicadores
            'bilionário',
            'bilionários',
            'ranking',
            'liderança',
            'primeiro',
            'melhor'
        ]

        negative_words = [
            # Economia geral
            'queda',
            'baixa',
            'caiu',
            'redução',
            'perda',
            'prejuízo',
            'crise',
            'recessão',
            'desemprego',
            'inflação',
            'déficit',
            'deterioração',
            'declínio',
            'contração',
            # Mercado financeiro
            'desvalorização',
            'calote',
            'inadimplência',
            'falência',
            'liquidação',
            'crash',
            # Política/conflitos
            'intimidação',
            'resistir',
            'conflito',
            'tensão',
            'disputa',
            'impasse',
            'sanção',
            'guerra',
            'ameaça',
            'retaliação',
            'embargo',
            'bloqueio',
            # Problemas sociais
            'corrupção',
            'escândalo',
            'investigação',
            'denúncia',
            'fraude'
        ]

        neutral_indicators = [
            'confirma', 'anuncia', 'divulga', 'informa', 'comunica', 'declara',
            'afirma', 'processo', 'reunião', 'encontro', 'conversa', 'telefone'
        ]

        # Contagem de palavras
        positive_count = sum(1 for word in positive_words
                             if word in text_lower)
        negative_count = sum(1 for word in negative_words
                             if word in text_lower)
        neutral_count = sum(1 for word in neutral_indicators
                            if word in text_lower)

        # Análise mais refinada
        total_sentiment_words = positive_count + negative_count

        if total_sentiment_words == 0:
            # Se não há palavras de sentimento, verifica contexto neutro
            if neutral_count > 0:
                return 'neutral'
            # Se não há indicadores claros, assume neutro
            return 'neutral'

        # Calcula percentual de sentimento
        positive_ratio = positive_count / total_sentiment_words if total_sentiment_words > 0 else 0
        negative_ratio = negative_count / total_sentiment_words if total_sentiment_words > 0 else 0

        # Define limiar mais baixo para detectar sentimento
        if positive_ratio > 0.6 or (positive_count > negative_count
                                    and positive_count >= 1):
            return 'positive'
        elif negative_ratio > 0.6 or (negative_count > positive_count
                                      and negative_count >= 1):
            return 'negative'
        else:
            return 'neutral'


# Classe para gerenciamento do banco de dados
class DatabaseManager:

    def __init__(self, db_name='news.db'):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS news
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             title TEXT,
             summary TEXT,
             link TEXT,
             source TEXT,
             sentiment TEXT,
             date TEXT)
        ''')
        conn.commit()
        conn.close()

    def save_news(self, news_items):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()

        for news in news_items:
            c.execute(
                '''
                INSERT INTO news (title, summary, link, source, sentiment, date)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (news['title'], news['summary'], news['link'], news['source'],
                  news['sentiment'], news['date']))

        conn.commit()
        conn.close()

    def get_recent_news(self, limit=20):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute(
            '''
            SELECT * FROM news 
            ORDER BY date DESC 
            LIMIT ?
        ''', (limit, ))

        columns = [description[0] for description in c.description]
        news_items = [dict(zip(columns, row)) for row in c.fetchall()]

        conn.close()
        return news_items

    def get_sentiment_stats(self):
        conn = sqlite3.connect(self.db_name)
        c = conn.cursor()
        c.execute('''
            SELECT sentiment, COUNT(*) as count 
            FROM news 
            WHERE date >= datetime('now', '-1 day')
            GROUP BY sentiment
        ''')

        stats = {row[0]: row[1] for row in c.fetchall()}

        # Garantir que todas as categorias existam
        for sentiment in ['positive', 'neutral', 'negative']:
            if sentiment not in stats:
                stats[sentiment] = 0

        conn.close()
        return stats


# Funções para visualização
def create_sentiment_chart(stats):
    labels = list(stats.keys())
    values = list(stats.values())

    colors = ['green', 'gray', 'red']

    fig = go.Figure(data=[
        go.Pie(labels=labels, values=values, marker=dict(colors=colors))
    ])

    fig.update_layout(title_text="Distribuição de Sentimentos (Últimas 24h)",
                      title_x=0.5)

    return fig.to_html()


def create_timeline_chart(news_items):
    # Verificar se há dados
    if not news_items:
        fig = go.Figure()
        fig.add_annotation(text="Aguardando dados...",
                           xref="paper",
                           yref="paper",
                           x=0.5,
                           y=0.5,
                           xanchor='center',
                           yanchor='middle',
                           showarrow=False,
                           font=dict(size=16))
        fig.update_layout(
            title_text="Evolução de Sentimentos ao Longo do Tempo",
            title_x=0.5,
            showlegend=False)
        return fig.to_html()

    # Agrupar notícias por hora e sentimento
    df = pd.DataFrame(news_items)
    df['date'] = pd.to_datetime(df['date'])
    df['hour'] = df['date'].dt.floor('H')

    timeline = df.groupby(['hour', 'sentiment']).size().unstack(fill_value=0)

    fig = go.Figure()

    colors = {'positive': 'green', 'neutral': 'gray', 'negative': 'red'}

    for sentiment in timeline.columns:
        fig.add_trace(
            go.Scatter(x=timeline.index,
                       y=timeline[sentiment],
                       mode='lines+markers',
                       name=sentiment,
                       line=dict(color=colors.get(sentiment, 'blue'))))

    fig.update_layout(title_text="Evolução de Sentimentos ao Longo do Tempo",
                      xaxis_title="Hora",
                      yaxis_title="Número de Notícias",
                      title_x=0.5)

    return fig.to_html()


# Aplicação Flask
@app.route('/')
def dashboard():
    db_manager = DatabaseManager()
    news_items = db_manager.get_recent_news(10)
    stats = db_manager.get_sentiment_stats()

    sentiment_chart = create_sentiment_chart(stats)
    timeline_chart = create_timeline_chart(news_items)

    return render_template(
        'dashboard.html',
        news_items=news_items,
        sentiment_chart=sentiment_chart,
        timeline_chart=timeline_chart,
        last_update=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/api/news')
def api_news():
    db_manager = DatabaseManager()
    news_items = db_manager.get_recent_news(20)
    return jsonify(news_items)


@app.route('/api/stats')
def api_stats():
    db_manager = DatabaseManager()
    stats = db_manager.get_sentiment_stats()
    return jsonify(stats)


# Função para atualizar notícias automaticamente
def scheduled_task():
    scraper = NewsScraper()
    db_manager = DatabaseManager()

    print(
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Coletando notícias..."
    )

    news_items = scraper.scrape_news()
    db_manager.save_news(news_items)

    print(
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {len(news_items)} notícias salvas."
    )


def run_scheduler():
    # Executa imediatamente ao iniciar
    scheduled_task()

    # Agenda para executar a cada hora
    schedule.every(1).hours.do(scheduled_task)

    while True:
        schedule.run_pending()
        time.sleep(1)


# Template HTML para o dashboard
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monitor de Sentimentos - Notícias Econômicas</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .chart-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .news-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .news-item { border-bottom: 1px solid #eee; padding: 15px 0; }
        .news-item:last-child { border-bottom: none; }
        .news-title { font-weight: bold; color: #333; margin-bottom: 5px; }
        .news-summary { color: #666; margin-bottom: 5px; font-size: 14px; }
        .news-meta { font-size: 12px; color: #999; }
        .sentiment-badge { padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase; }
        .sentiment-positive { background-color: #d4edda; color: #155724; }
        .sentiment-negative { background-color: #f8d7da; color: #721c24; }
        .sentiment-neutral { background-color: #e2e3e5; color: #383d41; }
        .last-update { text-align: center; margin-top: 20px; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Monitor de Sentimentos - Notícias Econômicas</h1>
            <p>Análise automática de sentimentos das notícias econômicas brasileiras</p>
        </div>

        <div class="stats">
            <div class="chart-container">
                {{ sentiment_chart|safe }}
            </div>
            <div class="chart-container">
                {{ timeline_chart|safe }}
            </div>
        </div>

        <div class="news-container">
            <h2>Notícias Recentes</h2>
            {% for news in news_items %}
            <div class="news-item">
                <div class="news-title">{{ news.title }}</div>
                {% if news.summary %}
                <div class="news-summary">{{ news.summary }}</div>
                {% endif %}
                <div class="news-meta">
                    <span class="sentiment-badge sentiment-{{ news.sentiment }}">{{ news.sentiment }}</span>
                    {{ news.source }} - {{ news.date }}
                </div>
            </div>
            {% endfor %}
        </div>

        <div class="last-update">
            Última atualização: {{ last_update }}
        </div>
    </div>
</body>
</html>'''

# Criar diretório de templates e salvar o template HTML
import os
if not os.path.exists('templates'):
    os.makedirs('templates')

with open('templates/dashboard.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

# Inicialização
if __name__ == '__main__':
    # Iniciar o agendador em uma thread separada
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    # Iniciar a aplicação Flask
    print("Iniciando dashboard em http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
