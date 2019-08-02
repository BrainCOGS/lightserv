from lightserv import create_demo_app, config

app = create_demo_app(config.DemoConfig)

if __name__ == '__main__':
	app.run()