import fractions # For making nice ratios
from anytree import Node, Walker, WalkError
from anytree.exporter import DotExporter
from IPython.display import Image
from fractions import Fraction

class Recipe(object):
    def __init__(self,rdict):
        self.time = rdict['energy']
        self.name = rdict['name']
        self.ingredients = rdict['ingredients']
        self.products = {}
        self.ingredients = {}
        for prod in rdict['products']:
            if 'amount' in prod.keys():
                self.products[prod['name']] = {'amount': prod['amount']}
            else:
                self.products[prod['name']] = {'amount': prod['probability']}
        for ing in rdict['ingredients']:
            self.ingredients[ing['name']] = {'amount': ing['amount']}

        self.category = rdict['category']

    def __repr__(self):
        dstr = self.name+'\n'
        dstr += 'Ingredients: \n'
        for ing, vals in self.ingredients.items():
            dstr += '    '+str(vals['amount']) + ' ' + ing +'\n'
        dstr += 'Products: \n'
        for prod, vals in self.products.items():
            dstr += '    '+str(vals['amount']) + ' ' + prod +'\n'
        dstr += 'Time: '+str(self.time)+'\n'
        dstr += '\n\n'
        return dstr

class Machine(object):
    def __init__(self,rdict):
        self.name = rdict['name']
        self.speed = rdict['craftingSpeed']
        self.max_ingredients = rdict['ingredientCount']
        self.categories = []
        #self.energy_usage = rdict['energyUsage']
        for category, enabled in rdict['categories'].items():
            if enabled:
                self.categories.append(category)

    def __repr__(self):
        dstr = self.name+'\n'
        dstr += 'Speed: '+str(self.speed)+'\n'
        dstr += 'Categories: \n'
        for category in self.categories:
            dstr += '    '+category+'\n'
        return dstr

class Cookbook(object):
    """A set of recipes and machines."""

    def __init__(self, recipes, machines):
        self.recipes = recipes
        self.machines = machines

        all_items = set()
        for recip in recipes.values():
            for ing in recip.ingredients:
                all_items.add(ing)
            for prod in recip.products:
                all_items.add(prod)
        self.all_items = all_items

        all_items = list(self.all_items)
        product_appearances = [0]*len(all_items)

        for recip in self.recipes.values():
            for product in recip.products:
                i = all_items.index(product)
                product_appearances[i] += 1

        self.one_recipe_items = [item for j, item in enumerate(all_items) if product_appearances[j] == 1]
        self.composite_recipe_items = {}
        self.chosen_recipe_items = {}

    def find_machines(self, recipe):
        """List all the machines capable of crafting the given recipe.
           The recipe can be specified as a string or a recipe object."""
        if type(recipe)==str: recipe = self.recipes[recipe]
        capable_machines = []
        category = recipe.category
        for machine_name, machine_values in self.machines.items():
            if category in machine_values.categories:
                capable_machines.append(machine_name)
        return capable_machines

    def search_recipes(self,partname):
        "List all recipe names containing the specified substring."
        for rec in self.recipes:
            if partname in rec: print(rec)

    def machine_ratio(self,production_recipe,machine1,consumption_recipe,machine2,item=None):
        """Give number of machine1's to exactly supply 1 machine2 with whatever the common item is."""
        if item is None:
            item = production_recipe
        production_recipe = self.recipes[production_recipe]
        consumption_recipe = self.recipes[consumption_recipe]
        machine1 = self.machines[machine1]
        machine2 = self.machines[machine2]
        numout = production_recipe.products[item]['amount']
        numin  = consumption_recipe.ingredients[item]['amount']
        rate1 = numout * machine1.speed / production_recipe.time
        rate2 = numin * machine2.speed / consumption_recipe.time
        ratio = rate2/rate1
        frac = fractions.Fraction(ratio).limit_denominator(100)
        print('Exact:', ratio)
        print('Approx:', frac.numerator, ':', frac.denominator)

    def find_consumers(self,item):
        "Find all recipes that can use the specified item."
        consumers = []
        for recipe_name, recipe in self.recipes.items():
            if item in recipe.ingredients:
                consumers.append(recipe_name)
        return consumers

    def find_producers(self,item):
        "Find all recipes that produce the specified item."
        producers = []
        for recipe_name, recipe in self.recipes.items():
            if item in recipe.products:
                producers.append(recipe_name)
        return producers

    def find_chains(self, item_in, item_out, max_path_length=5, exclusions=()):
        """Find all ways to produce item_out from item_in using no more than max_path_length recipes.
           Ignore any recipes where one of exclusions is part of a recipe name.
           A production chain is represented as an alternating sequence of recipes and items.
           """
        production_chains = []  # Temporary storage
        valid_production_chains = []  # Chains that lead from in to out
        additional_ingredients_valid = []
        additional_products_valid = []

        # Check that specified items exist
        if item_in not in self.all_items:
            raise Exception('input item '+item_in+' does not exist.')
        if item_out not in self.all_items:
            raise Exception('output item '+item_out+' does not exist.')

        # Find immediate products
        for recipe in self.find_consumers(item_in):
            if check_exclusions(recipe,exclusions):  # Recipe is allowed
                if item_out in self.recipes[recipe].products:
                    valid_production_chains.append([item_in, recipe, item_out])
                    for prod in self.recipes[recipe].products:
                        if prod != item_out:
                            additional_products_valid.append(prod)
                    for ing in self.recipes[recipe].ingredients:
                        if ing != item_in:
                            additional_ingredients_valid.append(ing)

                else:  # Assume there are no loops
                    production_chains.append([item_in, recipe])

        for _ in range(max_path_length-1):
            new_production_chains = []
            for __, prodchain in enumerate(production_chains):
                last_recipe = self.recipes[prodchain[-1]]
                # Look 1 level deeper
                for product in last_recipe.products:
                    for recipe in self.find_consumers(product):
                        if check_exclusions(recipe,exclusions):
                            if item_out in self.recipes[recipe].products:
                                valid_production_chains.append(prodchain+[product, recipe, item_out])
                            else:
                                new_production_chains.append(prodchain+[product, recipe])

            production_chains = new_production_chains

        return valid_production_chains

    def calculate_yield(self,production_chain):
        """Return the number of final outputs produced per first input.
        """
        overall_yield = 1
        for i in range(1,len(production_chain),2):
            recipe = self.recipes[production_chain[i]]
            item_in = production_chain[i-1]
            item_out = production_chain[i+1]
            yield_factor = recipe.products[item_out]['amount']/recipe.ingredients[item_in]['amount']
            overall_yield *= yield_factor
        return overall_yield

    def machines_needed(self,output_quantity,production_chain):
        """Determine how many machines are needed at each step to get output_quantity per second.

           The production_chain should come from find_chains().  The fastest machines from
           machines_available will be used.
        """
        # First determine how many we need per second of each intermediate
        items = chain_items(production_chain)
        ch_recipes = chain_recipes(production_chain)
        yield_factors = []
        quantity_out = []
        for i in range(1,len(production_chain),2):
            recipe = self.recipes[production_chain[i]]
            item_in = production_chain[i-1]
            item_out = production_chain[i+1]
            quantity_out.append(recipe.products[item_out]['amount'])
            yield_factors.append(recipe.products[item_out]['amount']/recipe.ingredients[item_in]['amount'])

        number_needed = [output_quantity]
        for i in range(len(items)-2,-1,-1):
            number_needed.insert(0,number_needed[0]/yield_factors[i])

        # Now find the appropriate (fastest) machine
        machines_to_use = []
        for recipe in ch_recipes:
            potential_machines = self.find_machines(recipe)
            fastest = self.machines[potential_machines[0]]
            for machine in potential_machines[1:]:
                m = self.machines[machine]
                if m.speed > fastest.speed:
                    fastest = m
            machines_to_use.append(fastest.name)

        # Compute number of machines needed
        machines_needed = []
        for i, recipe in enumerate(ch_recipes):
            machines_needed.append(number_needed[i+1] /
                    self.machines[machines_to_use[i]].speed *
                    self.recipes[recipe].time/quantity_out[i])
        return list(zip(machines_to_use,machines_needed))


    def all_ingredients(self,production_chain,output_quantity=1):
        """Determine all the ingredients needed to get output_quantity items using this production chain.
           (not counting intermediates that are produced and consumed).

           The production_chain should come from find_chains().
        """
        ingredients = []
        # First determine how many we need of each intermediate
        items = chain_items(production_chain)
        ch_recipes = chain_recipes(production_chain)
        yield_factors = []
        for i in range(len(ch_recipes)):
            recipe = self.recipes[ch_recipes[i]]
            item_in = items[i]
            item_out = items[i+1]
            yield_factors.append(recipe.products[item_out]['amount']/recipe.ingredients[item_in]['amount'])

        number_needed = [output_quantity]  # How many we need of the output of recipe i
        for i in range(len(items)-2,-1,-1):
            number_needed.insert(0,number_needed[0]/yield_factors[i])

        for i, recipe in enumerate(ch_recipes):
            multiplier = number_needed[i+1]/self.recipes[recipe].products[items[i+1]]['amount']
            for ing in self.recipes[recipe].ingredients:
                if ing != items[i] or i==0:  # Skip intermediates that are already accounted for
                    ingredients.append((ing,multiplier*self.recipes[recipe].ingredients[ing]['amount']))

        return ingredients

    def all_products(self,production_chain,output_quantity=1):
        """Determine all the outputs created to get output_quantity items using this production chain
           (not counting intermediates that are produced and consumed within the chain).

           The production_chain should come from find_chains().
        """
        products = []
        # First determine how many we need of each intermediate
        items = chain_items(production_chain)
        ch_recipes = chain_recipes(production_chain)
        yield_factors = []
        for i in range(len(ch_recipes)):
            recipe = self.recipes[ch_recipes[i]]
            item_in = items[i]
            item_out = items[i+1]
            yield_factors.append(recipe.products[item_out]['amount']/recipe.ingredients[item_in]['amount'])

        number_needed = [output_quantity]  # How many we need of the output of recipe i
        for i in range(len(items)-2,-1,-1):
            number_needed.insert(0,number_needed[0]/yield_factors[i])

        for i, recipe in enumerate(ch_recipes):
            multiplier = number_needed[i+1]/self.recipes[recipe].products[items[i+1]]['amount']
            for prod in self.recipes[recipe].products:
                if prod != items[i+1] or i==len(ch_recipes)-1:  # Skip intermediates that are already accounted for
                    products.append((prod,multiplier*self.recipes[recipe].products[prod]['amount']))

        return products

    def add_recipe_and_ingredients(self, item_node, use_composites=False, recipe=None, show_options=False,
                                   preferred_recipes=()):
        # A composite recipe is a way of squashing the tree, directly linking an output
        # with the base inputs
        # At present this must be done manually; it would be nice to automate it.
        new_nodes = []
        item = item_node.name
        if item in self.composite_recipe_items and use_composites:
            recipe = self.composite_recipe_items[item]
        elif item in self.chosen_recipe_items:
            recipe = self.chosen_recipe_items[item]
        elif item in self.one_recipe_items and item != 'water':
            recipe = self.find_producers(item)[0]
        else:
            options = self.find_producers(item)
            for option in options:
                if option in preferred_recipes:
                    recipe = option
        if recipe:
            new_nodes.append(Node(recipe+'-recipe',parent=item_node,flag='recipe',
                                  number=self.recipes[recipe].products[item]['amount'],
                                  shape='box'))
            rec_node = new_nodes[-1]
            for ing in self.recipes[recipe].ingredients:
                new_nodes.append(Node(ing,parent=rec_node,flag='item',
                                      number=self.recipes[recipe].ingredients[ing]['amount']))
        else:
            if show_options:
                options = self.find_producers(item)
                if len(options)>10:
                    new_nodes.append(Node('Too many recipes to show',parent=item_node,flag='option',number=1))
                else:
                    for option in options:
                        new_nodes.append(Node(option+' ',parent=item_node,flag='option',
                                              number=self.recipes[option].products[item]['amount'],
                                              shape='box'))
        return new_nodes

    def production_tree(self,output_item,quantity=1,maxdepth=10,commodities=(),use_composites=False, show_options=False,
                        preferred_recipes=()):
        tree = [Node(output_item,flag='item',number=quantity,needed=quantity)]
        tree = tree + self.add_recipe_and_ingredients(tree[0],use_composites,show_options=show_options,
                                                      preferred_recipes=preferred_recipes)

        for _ in range(maxdepth):
            new_nodes = []
            for node in tree:
                if node.is_leaf and node.name not in commodities:
                    new_nodes += self.add_recipe_and_ingredients(node,use_composites,show_options=show_options,
                                                                 preferred_recipes=preferred_recipes)
            tree += new_nodes

        set_needs(tree)
        self.set_machines(tree)
        return tree

    def set_machines(self,tree):
        """Determine number and type of machines used to produce 1 final output per second."""
        for node in tree:
            if node.flag == 'recipe':
                recipe = self.recipes[node.name[:-7]]  # Remove "-recipe"
                # Now find the appropriate (fastest) machine
                potential_machines = self.find_machines(recipe)
                machine_type = self.machines[potential_machines[0]]
                for machine in potential_machines[1:]:
                    m = self.machines[machine]
                    if m.speed > machine_type.speed:
                        machine_type = m
                # Compute number of machines needed
                machines_needed = node.needed * recipe.time / machine_type.speed
                node.machine_type = machine_type.name
                node.machines = machines_needed


def show_tree(tree, number_out=1):
    def edgetypefunc(node, child):
        return '--'

    def nodeattrfunc(node):
        attrs = ''
        if node.flag == 'option':
            attrs += "color=grey, fontcolor=grey, "
        if node.flag == 'recipe':
            attrs += "shape=box, color=red, fontsize=12, "
        if node.flag == 'item':
            attrs += "shape=ellipse, "
        #if node.flag == 'item' and 'plate' in node.name:
        #    attrs += "style=filled, fillcolor=grey, "
        #if node.flag == 'item' and 'ore' in node.name:
        #    attrs += "style=filled, fillcolor=lightblue, "
        if node.is_leaf and node.flag != 'option':
            attrs += "style=filled, fillcolor=grey, "
        return attrs

    def nodenamefunc(node):
        if node.flag == 'item':
            f = Fraction(node.needed*number_out)
            return '{1}\n{0}'.format(node.name, f.limit_denominator(100))
        elif node.flag == 'recipe':
            f = Fraction(node.machines*number_out)
            return '{}\n{} {}'.format(node.name, f.limit_denominator(100), node.machine_type)
        elif node.flag == 'option':
            return node.name

    DotExporter(tree[0],graph='graph',
                edgetypefunc=edgetypefunc,
                nodeattrfunc=nodeattrfunc,
                nodenamefunc=nodenamefunc).to_picture("temp.png")
    return Image("./temp.png")

def set_needs(tree):
    """For a recipe, needed is the number of times it must be run for 1 final output.

       For an item, needed is the number that must be produced for 1 final output.
    """
    w=Walker()
    for leaf in tree:
        if leaf.is_leaf:
            needed = tree[0].number
            try:
                for i, node in enumerate(w.walk(tree[0],leaf)[2]):
                    if i % 2 == 0:  # recipe node
                        needed /= node.number
                    else:  # item node
                        needed *= node.number
                    node.needed = needed
            except WalkError:
                pass

def all_ingredients(tree, number_out=1):
    """Gives all the base ingredients required by a production tree."""
    ingredients = {}
    for node in tree:
        if node.is_leaf and node in tree[0].descendants:
            if node.name in ingredients:
                ingredients[node.name] += node.needed*number_out
            else:
                ingredients[node.name] = node.needed*number_out
    return ingredients

def sum_ingredients(dict_list):
    """Add up all ingredients for a group of production trees."""
    total_ingredients = {}
    for ing_list in dict_list:
        for ingredient, quantity in ing_list.items():
            if ingredient in total_ingredients:
                total_ingredients[ingredient] += quantity
            else:
                total_ingredients[ingredient] = quantity
    return total_ingredients


def chain_recipes(production_chain):
    return production_chain[1:-1:2]

def chain_items(production_chain):
    return production_chain[0::2]

def check_exclusions(name, substrings):
    "Returns True if no element of substrings is part of name."
    for ss in substrings:
        if ss in name:
            return False
    return True




