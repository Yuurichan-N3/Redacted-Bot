from aiohttp import (
    ClientResponseError,
    ClientSession,
    ClientTimeout
)
from datetime import datetime
from fake_useragent import FakeUserAgent
import asyncio, base64, json, os, pytz
from aiohttp_socks import ProxyConnector
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
import logging
from rich.theme import Theme
from rich.style import Style

# Configure Rich Console with custom theme
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "red",
    "success": "green"
})
console = Console(theme=custom_theme)

# Configure logging with RichHandler
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("RedactedAirways")

wib = pytz.timezone('Asia/Jakarta')

class RedactedAirways:
    def __init__(self) -> None:
        self.headers = {
            'Accept': '*/*',
            'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://quest.redactedairways.com/home',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': FakeUserAgent().random
        }
        self.proxies = []
        self.proxy_index = 0
        self.account_proxies = {}
        self.console = console

    def clear_terminal(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def welcome(self):
        self.console.print("""
        [success]RedactedAirways Quests - BOT[/success]
        """)

    def format_seconds(self, seconds):
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

    async def load_proxies(self, use_proxy_choice: int):
        filename = "proxy.txt"
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn()
            ) as progress:
                task = progress.add_task("[cyan]Loading proxies...", total=None)
                
                if use_proxy_choice == 1:
                    async with ClientSession(timeout=ClientTimeout(total=30)) as session:
                        async with session.get("https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt") as response:
                            response.raise_for_status()
                            content = await response.text()
                            with open(filename, 'w') as f:
                                f.write(content)
                            self.proxies = content.splitlines()
                else:
                    if not os.path.exists(filename):
                        logger.error("File proxy.txt Not Found.")
                        return
                    with open(filename, 'r') as f:
                        self.proxies = f.read().splitlines()

                if not self.proxies:
                    logger.error("No Proxies Found.")
                    return

                progress.update(task, completed=100)
                logger.info(f"Loaded {len(self.proxies)} proxies successfully")

        except Exception as e:
            logger.error(f"Failed To Load Proxies: {e}")
            self.proxies = []

    def create_proxy_table(self):
        table = Table(title="Proxy Statistics")
        table.add_column("Type", style="cyan")
        table.add_column("Count", style="green")
        table.add_column("Status", style="yellow")
        
        proxy_types = {
            "http": len([p for p in self.proxies if p.startswith(("http://", "https://"))]),
            "socks4": len([p for p in self.proxies if p.startswith("socks4://")]),
            "socks5": len([p for p in self.proxies if p.startswith("socks5://")]),
        }
        
        for proxy_type, count in proxy_types.items():
            status = "✓ Active" if count > 0 else "✗ None"
            table.add_row(proxy_type.upper(), str(count), status)
            
        return table

    def check_proxy_schemes(self, proxies):
        schemes = ["http://", "https://", "socks4://", "socks5://"]
        if any(proxies.startswith(scheme) for scheme in schemes):
            return proxies
        return f"http://{proxies}"

    def get_next_proxy_for_account(self, address):
        if address not in self.account_proxies:
            if not self.proxies:
                return None
            proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
            self.account_proxies[address] = proxy
            self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return self.account_proxies[address]

    def rotate_proxy_for_account(self, address):
        if not self.proxies:
            return None
        proxy = self.check_proxy_schemes(self.proxies[self.proxy_index])
        self.account_proxies[address] = proxy
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy

    def print_question(self):
        table = Table(title="Proxy Configuration Options")
        table.add_column("Option", style="cyan")
        table.add_column("Description", style="green")
        
        table.add_row("1", "Run With Monosans Proxy")
        table.add_row("2", "Run With Private Proxy")
        table.add_row("3", "Run Without Proxy")
        
        self.console.print(table)
        
        while True:
            try:
                choose = int(self.console.input("[cyan]Choose [1/2/3] -> [/cyan]").strip())
                if choose in [1, 2, 3]:
                    proxy_type = (
                        "Run With Monosans Proxy" if choose == 1 else 
                        "Run With Private Proxy" if choose == 2 else 
                        "Run Without Proxy"
                    )
                    logger.info(f"Selected: {proxy_type}")
                    return choose
                else:
                    logger.warning("Please enter either 1, 2 or 3.")
            except ValueError:
                logger.error("Invalid input. Enter a number (1, 2 or 3).")

    def decode_token(self, token: str):
        try:
            header, payload, signature = token.split(".")
            decoded_payload = base64.urlsafe_b64decode(payload + "==").decode("utf-8")
            parsed_payload = json.loads(decoded_payload)
            return parsed_payload.get("user_name", "Unknown")
        except Exception:
            return None

    def save_new_token(self, old_token, new_token):
        file_path = 'data.txt'
        with open(file_path, 'r') as file:
            tokens = [line.strip() for line in file if line.strip()]
        
        updated_tokens = [new_token if token == old_token else token for token in tokens]
        
        with open(file_path, 'w') as file:
            file.write("\n".join(updated_tokens) + "\n")

    async def revalidate_token(self, token: str, proxy=None, retries=5):
        url = 'https://quest.redactedairways.com/ecom-gateway/revalidate'
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}',
            'Content-Length': '0',
            'Origin': 'https://quest.redactedairways.com',
        }
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            task = progress.add_task("[cyan]Revalidating token...", total=retries)
            
            for attempt in range(retries):
                progress.update(task, completed=attempt)
                connector = ProxyConnector.from_url(proxy) if proxy else None
                try:
                    async with ClientSession(connector=connector, timeout=ClientTimeout(total=20)) as session:
                        async with session.post(url=url, headers=headers) as response:
                            response.raise_for_status()
                            result = await response.json()
                            return result["token"]
                except (Exception, ClientResponseError) as e:
                    if attempt < retries - 1:
                        await asyncio.sleep(5)
                        continue
                    return None

    async def user_auth(self, token: str, proxy=None, retries=3):
        """
        Verifies if the provided token is valid
        """
        url = 'https://quest.redactedairways.com/api/v1/user/auth'
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}'
        }
        
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=20)) as session:
                    async with session.get(url=url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()
                        return result.get("success", False)
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Auth verification failed: {e}")
                return False

    async def user_info(self, token: str, proxy=None, retries=3):
        """
        Gets user information including points balance
        """
        url = 'https://quest.redactedairways.com/api/v1/user/info'
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}'
        }
        
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=20)) as session:
                    async with session.get(url=url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()
                        return result.get("data", {})
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Failed to get user info: {e}")
                return None

    async def task_lists(self, token: str, task_type: str, proxy=None, retries=3):
        """
        Gets list of tasks based on the specified task type
        
        Parameters:
        - token: User authentication token
        - task_type: Type of task lists to retrieve ('task/list' or 'partners')
        - proxy: Optional proxy to use for request
        - retries: Number of retry attempts
        
        Returns:
        - Dictionary with task list data or None on failure
        """
        base_url = 'https://quest.redactedairways.com/api/v1/'
        url = f"{base_url}{task_type}"
        
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}'
        }
        
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=30)) as session:
                    async with session.get(url=url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()
                        return result
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    logger.warning(f"Attempt {attempt+1} failed for {task_type}. Retrying...")
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Failed to get {task_type} tasks: {e}")
                return None

    async def claim_task(self, token: str, task_id: str, proxy=None, retries=3):
        """
        Claims a task for the user
        
        Parameters:
        - token: User authentication token
        - task_id: ID of the task to claim
        - proxy: Optional proxy to use for request
        - retries: Number of retry attempts
        
        Returns:
        - True if task was claimed successfully, False otherwise
        """
        url = f'https://quest.redactedairways.com/api/v1/task/claim/{task_id}'
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=20)) as session:
                    async with session.post(url=url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()
                        success = result.get("success", False)
                        if success:
                            logger.info(f"Successfully claimed task {task_id}")
                            return True
                        else:
                            logger.warning(f"Failed to claim task {task_id}: {result.get('message', 'Unknown error')}")
                            return False
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Error claiming task {task_id}: {e}")
                return False

    async def complete_task(self, token: str, task_id: str, proxy=None, retries=3):
        """
        Marks a task as completed
        
        Parameters:
        - token: User authentication token
        - task_id: ID of the task to complete
        - proxy: Optional proxy to use for request
        - retries: Number of retry attempts
        
        Returns:
        - Task completion data or None on failure
        """
        url = f'https://quest.redactedairways.com/api/v1/task/complete/{task_id}'
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=20)) as session:
                    async with session.post(url=url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()
                        if result.get("success", False):
                            points_earned = result.get("data", {}).get("score", 0)
                            logger.info(f"Task {task_id} completed! Earned {points_earned} points")
                            return result.get("data")
                        else:
                            logger.warning(f"Task completion failed: {result.get('message', 'Unknown error')}")
                            return None
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Error completing task {task_id}: {e}")
                return None

    async def claim_partner_reward(self, token: str, partner_id: str, proxy=None, retries=3):
        """
        Claims a reward from a partner task
        
        Parameters:
        - token: User authentication token
        - partner_id: ID of the partner task
        - proxy: Optional proxy to use for request
        - retries: Number of retry attempts
        
        Returns:
        - Reward data or None on failure
        """
        url = f'https://quest.redactedairways.com/api/v1/partners/claim/{partner_id}'
        headers = {
            **self.headers,
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        for attempt in range(retries):
            connector = ProxyConnector.from_url(proxy) if proxy else None
            try:
                async with ClientSession(connector=connector, timeout=ClientTimeout(total=20)) as session:
                    async with session.post(url=url, headers=headers) as response:
                        response.raise_for_status()
                        result = await response.json()
                        if result.get("success", False):
                            points_earned = result.get("data", {}).get("score", 0)
                            logger.info(f"Partner reward {partner_id} claimed! Earned {points_earned} points")
                            return result.get("data")
                        else:
                            logger.warning(f"Partner reward claim failed: {result.get('message', 'Unknown error')}")
                            return None
            except (Exception, ClientResponseError) as e:
                if attempt < retries - 1:
                    await asyncio.sleep(5)
                    continue
                logger.error(f"Error claiming partner reward {partner_id}: {e}")
                return None

    async def process_accounts(self, token: str, username: str, use_proxy):
        proxy = self.get_next_proxy_for_account(username) if use_proxy else None
        new_token = None

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn()
        ) as progress:
            main_task = progress.add_task(f"[cyan]Processing account: {username}", total=100)

            # Token validation
            is_valid = await self.user_auth(token, proxy)
            if not is_valid:
                logger.warning("Token expired - attempting revalidation")
                new_token = await self.revalidate_token(token, proxy)
                if not new_token:
                    logger.error("Token revalidation failed")
                    return
                self.save_new_token(token, new_token)
                logger.info("Token revalidation successful")

            active_token = new_token if new_token else token
            progress.update(main_task, completed=20)

            # User info and balance
            user = await self.user_info(active_token, proxy)
            balance = user.get("overall_score", 0) if user else "N/A"
            logger.info(f"Current balance: {balance} Points")
            progress.update(main_task, completed=40)

            # Process tasks
            task_types = ["task/list", "partners"]
            for task_type in task_types:
                task_progress = progress.add_task(
                    f"[yellow]Processing {task_type}...",
                    total=100
                )
                
                task_lists = await self.task_lists(active_token, task_type, proxy)
                if task_lists:
                    if task_type == "task/list":
                        tasks = task_lists.get("list", [])
                        total_tasks = len(tasks)
                        for idx, task in enumerate(tasks, 1):
                            if task:
                                task_id = task.get("id")
                                task_title = task.get("title", "Unknown Task")
                                task_status = task.get("status")
                                task_points = task.get("expected_score", 0)
                                
                                progress.update(
                                    task_progress, 
                                    description=f"[yellow]Processing task {idx}/{total_tasks}: {task_title}"
                                )
                                
                                if task_status == "NOT_STARTED":
                                    # Claim task
                                    claim_result = await self.claim_task(active_token, task_id, proxy)
                                    if claim_result:
                                        # Complete task
                                        complete_result = await self.complete_task(active_token, task_id, proxy)
                                        if complete_result:
                                            logger.info(f"Completed task: {task_title} (+{task_points} points)")
                                        else:
                                            logger.warning(f"Failed to complete task: {task_title}")
                                    else:
                                        logger.warning(f"Failed to claim task: {task_title}")
                                elif task_status == "CLAIMED":
                                    # Task already claimed, complete it
                                    complete_result = await self.complete_task(active_token, task_id, proxy)
                                    if complete_result:
                                        logger.info(f"Completed task: {task_title} (+{task_points} points)")
                                    else:
                                        logger.warning(f"Failed to complete task: {task_title}")
                                elif task_status == "COMPLETED":
                                    logger.info(f"Task already completed: {task_title}")
                                    
                                progress.update(task_progress, completed=(idx/total_tasks)*100)
                                await asyncio.sleep(5)
                    elif task_type == "partners":
                        partners = task_lists.get("data", [])
                        total_partners = len(partners)
                        for idx, partner in enumerate(partners, 1):
                            if partner:
                                partner_id = partner.get("id")
                                partner_name = partner.get("name", "Unknown Partner")
                                partner_status = partner.get("status")
                                partner_points = partner.get("expected_score", 0)
                                
                                progress.update(
                                    task_progress, 
                                    description=f"[yellow]Processing partner {idx}/{total_partners}: {partner_name}"
                                )
                                
                                if partner_status == "NOT_CLAIMED":
                                    # Claim partner reward
                                    claim_result = await self.claim_partner_reward(active_token, partner_id, proxy)
                                    if claim_result:
                                        logger.info(f"Claimed partner reward: {partner_name} (+{partner_points} points)")
                                    else:
                                        logger.warning(f"Failed to claim partner reward: {partner_name}")
                                elif partner_status == "CLAIMED":
                                    logger.info(f"Partner reward already claimed: {partner_name}")
                                    
                                progress.update(task_progress, completed=(idx/total_partners)*100)
                                await asyncio.sleep(5)
                else:
                    logger.error(f"No data available for {task_type}")
                
                progress.update(main_task, completed=70 if task_type == "task/list" else 100)

    async def main(self):
        try:
            with open('data.txt', 'r') as file:
                tokens = [line.strip() for line in file if line.strip()]

            use_proxy_choice = self.print_question()
            use_proxy = use_proxy_choice in [1, 2]
            
            if use_proxy:
                await self.load_proxies(use_proxy_choice)
                self.console.print(self.create_proxy_table())

            while True:
                self.clear_terminal()
                self.welcome()
                logger.info(f"Processing {len(tokens)} accounts")

                with ThreadPoolExecutor(max_workers=3) as executor:
                    tasks = []
                    for token in tokens:
                        if token:
                            username = self.decode_token(token)
                            if username:
                                task = self.process_accounts(token, username, use_proxy)
                                tasks.append(task)
                    
                    await asyncio.gather(*tasks)

                logger.info("All accounts processed. Starting countdown...")
                
                seconds = 12 * 60 * 60
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    transient=True
                ) as progress:
                    countdown = progress.add_task(
                        "[cyan]Time until next run",
                        total=seconds
                    )
                    while seconds > 0:
                        formatted_time = self.format_seconds(seconds)
                        progress.update(
                            countdown,
                            completed=seconds,
                            description=f"[cyan]Next run in: {formatted_time}"
                        )
                        await asyncio.sleep(1)
                        seconds -= 1
                        progress.update(countdown, completed=seconds)

        except FileNotFoundError:
            logger.error("File 'data.txt' Not Found.")
            return
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)

if __name__ == "__main__":
    try:
        bot = RedactedAirways()
        asyncio.run(bot.main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
